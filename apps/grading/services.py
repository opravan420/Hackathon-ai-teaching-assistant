import re
import json
import logging
from typing import List, Dict, Any
from django.db import transaction

from apps.grading.models import GradingSession, StudentGradingResult, QuestionScore
from apps.ai_engine.document_processing.service import DocumentService
from apps.ai_engine.prompting.prompt_builder import PromptBuilder
from apps.ai_engine.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class GradingError(Exception):
    """Raised when grading evaluation fails or inputs are invalid."""
    pass

class GradingService:
    """Core service for AI Student Short-Answer Grading."""

    def __init__(self):
        self.doc_service = DocumentService()
        self.prompt_builder = PromptBuilder()
        self.llm_service = LLMService()

    def grade_student_sheet(
        self,
        teacher,
        question_paper_file,
        student_answer_file,
        master_answer_file = None,
        rubric_file = None,
        evaluation_criteria: str = None,
        additional_instructions: str = None,
        student_name: str = "Student",
        default_max_marks: float = 5.0
    ) -> StudentGradingResult:
        """
        Evaluates a student's answer sheet question-by-question against optional master answer key and grading criteria.
        Criteria can be provided via uploaded rubric file OR manual evaluation instructions (XOR).
        """
        if not question_paper_file or not student_answer_file:
            raise ValueError("Question Paper and Student Answer Sheet are required.")

        has_file_rubric = bool(rubric_file)
        has_manual_rubric = bool(evaluation_criteria and evaluation_criteria.strip()) or bool(additional_instructions and additional_instructions.strip())

        if has_file_rubric and has_manual_rubric:
            raise ValueError("Please use either a grading criteria document or manual grading criteria, not both.")

        if not has_file_rubric and not has_manual_rubric:
            raise ValueError("Please either upload a grading criteria document or enter the grading criteria manually.")

        # Step 1: Process Question Paper, Master Answer (Optional), and Criteria
        qp_doc = self.doc_service.process_document(teacher, question_paper_file)
        
        ma_text = ""
        ma_name = "None"
        if master_answer_file:
            ma_doc = self.doc_service.process_document(teacher, master_answer_file)
            ma_text = ma_doc.extracted_text
            ma_name = ma_doc.original_filename
        else:
            ma_text = "No master answer key provided. Grade based on standard question requirements and grading criteria."

        rubric_text = ""
        rubric_name = "None"
        if has_file_rubric:
            r_doc = self.doc_service.process_document(teacher, rubric_file)
            rubric_text = r_doc.extracted_text
            rubric_name = r_doc.original_filename
        elif has_manual_rubric:
            parts = []
            if evaluation_criteria and evaluation_criteria.strip():
                parts.append(f"Evaluation Criteria:\n{evaluation_criteria.strip()}")
            if additional_instructions and additional_instructions.strip():
                parts.append(f"Additional Instructions:\n{additional_instructions.strip()}")
            rubric_text = "\n\n".join(parts)
            rubric_name = "Manual Criteria"

        # Step 2: Process Student Answer Sheet & Check Text Extraction
        try:
            student_doc = self.doc_service.process_document(teacher, student_answer_file)
            student_text = student_doc.extracted_text.strip()
        except Exception as e:
            raise GradingError(
                f"Could not extract readable text from student answer sheet: {str(e)}"
            )

        if not student_text:
            raise GradingError(
                "Could not extract readable text from student answer sheet. "
                "Image/handwritten scans without text layers cannot be graded automatically."
            )

        # Step 3: Parse questions and master answers into question blocks
        question_blocks = self._parse_question_blocks(qp_doc.extracted_text, ma_text, default_max_marks)

        if not question_blocks:
            # Fallback: treat entire document as single Question 1 if structure parsing is monolithic
            question_blocks = [{
                "question_number": "Q1",
                "question_text": qp_doc.extracted_text[:1000],
                "master_answer": ma_text[:1000],
                "max_marks": default_max_marks
            }]

        # Step 4: Evaluate question-by-question via LLM
        evaluated_scores = []
        for q_block in question_blocks:
            user_prompt, system_prompt = self.prompt_builder.build_grading_prompt(
                question_number=q_block["question_number"],
                question_text=q_block["question_text"],
                master_answer=q_block["master_answer"],
                criteria=rubric_text,
                student_answer=student_text,
                max_marks=q_block["max_marks"]
            )

            raw_response = self.llm_service.generate_text(prompt=user_prompt, system_prompt=system_prompt)
            eval_data = self._clean_and_parse_json(raw_response)
            validated_eval = self._validate_grading_schema(eval_data, q_block["question_number"], q_block["max_marks"])
            evaluated_scores.append(validated_eval)

        # Step 5: Save GradingSession, StudentGradingResult, and QuestionScore records
        with transaction.atomic():
            session = GradingSession.objects.create(
                teacher=teacher,
                question_paper_name=qp_doc.original_filename,
                master_answer_name=ma_name,
                rubric_name=rubric_name
            )

            total_score = sum(item["marks_awarded"] for item in evaluated_scores)
            max_score = sum(item["max_marks"] for item in evaluated_scores)
            overall_feedback = f"Graded {len(evaluated_scores)} questions. Total score: {total_score}/{max_score}."

            result = StudentGradingResult.objects.create(
                session=session,
                student_name=student_name.strip() if student_name else "Student",
                answer_sheet_name=student_doc.original_filename,
                total_score=round(total_score, 2),
                max_score=round(max_score, 2),
                overall_feedback=overall_feedback
            )

            for item in evaluated_scores:
                QuestionScore.objects.create(
                    grading_result=result,
                    question_number=item["question_number"],
                    max_score=item["max_marks"],
                    score_given=item["marks_awarded"],
                    feedback=item["feedback"]
                )

        return result

    def _parse_question_blocks(self, qp_text: str, ma_text: str, default_max: float) -> List[Dict[str, Any]]:
        """Parses question numbers, text, master answers, and max marks from texts."""
        # Look for patterns like Q1, Q2, Question 1, 1., etc.
        pattern = r'(?:Q|Question\s*)?(\d+)[\.\:\)]'
        qp_matches = list(re.finditer(pattern, qp_text, re.IGNORECASE))
        
        if not qp_matches:
            return []

        blocks = []
        for i, match in enumerate(qp_matches):
            q_num = f"Q{match.group(1)}"
            start_idx = match.start()
            end_idx = qp_matches[i+1].start() if i + 1 < len(qp_matches) else len(qp_text)
            q_text_segment = qp_text[start_idx:end_idx].strip()

            # Attempt to parse explicit max marks from question text, e.g., (5 Marks), [10m], (Marks: 5)
            marks_match = re.search(r'[\(\[]\s*(\d+(?:\.\d+)?)\s*(?:marks?|pts?|m)?\s*[\)\]]', q_text_segment, re.IGNORECASE)
            parsed_max = float(marks_match.group(1)) if marks_match else default_max

            blocks.append({
                "question_number": q_num,
                "question_text": q_text_segment[:800],
                "master_answer": ma_text[:1000],
                "max_marks": parsed_max
            })

        return blocks

    def _clean_and_parse_json(self, response_text: str) -> Dict[str, Any]:
        """Strips markdown block markers and parses JSON string."""
        clean_text = response_text.strip()
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()

        try:
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"Failed to parse LLM grading JSON response: {e}\nRaw output: {response_text[:300]}")
            raise GradingError("AI evaluation response was not valid structured JSON. Please try again.")

    def _validate_grading_schema(self, data: Dict[str, Any], question_num: str, max_marks: float) -> Dict[str, Any]:
        """Enforces score bounds: 0.0 <= marks_awarded <= max_marks."""
        if not isinstance(data, dict):
            raise GradingError(f"AI evaluation for {question_num} is not a valid JSON dictionary.")

        raw_awarded = data.get("marks_awarded", 0.0)
        try:
            awarded = float(raw_awarded)
        except (ValueError, TypeError):
            awarded = 0.0

        # Enforce bounds (Never allow negative marks or marks > max_marks)
        if awarded < 0.0:
            awarded = 0.0
        if awarded > max_marks:
            awarded = max_marks

        feedback = str(data.get("feedback", "Evaluated based on answer key.")).strip()

        return {
            "question_number": str(data.get("question_number", question_num)),
            "marks_awarded": round(awarded, 2),
            "max_marks": round(max_marks, 2),
            "feedback": feedback
        }
