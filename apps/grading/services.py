import re
import json
import logging
from typing import List, Dict, Any
from django.db import transaction
from django.utils import timezone

from apps.grading.models import GradingSession, StudentSubmission, StudentGradingResult, QuestionScore
from apps.ai_engine.document_processing.service import DocumentService
from apps.ai_engine.prompting.prompt_builder import PromptBuilder
from apps.ai_engine.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class GradingError(Exception):
    """Raised when grading evaluation fails or inputs are invalid."""
    pass

class GradingService:
    """Core service for AI Student Short-Answer Grading and Reusable Grading Sessions."""

    def __init__(self):
        self.doc_service = DocumentService()
        self.prompt_builder = PromptBuilder()
        self.llm_service = LLMService()
        from apps.ai_engine.task_tracker import TaskTracker
        self.task_tracker = TaskTracker()

    def create_grading_session(
        self,
        teacher,
        title: str,
        question_paper_file,
        master_answer_file=None,
        rubric_file=None,
        criteria_source: str = 'file',
        evaluation_criteria: str = None,
        additional_instructions: str = None,
        default_max_marks: float = 5.0
    ) -> GradingSession:
        """
        Processes common exam documents ONCE and saves a reusable GradingSession in READY status.
        """
        if not question_paper_file:
            raise ValueError("Question Paper document is required.")

        title = title.strip() if title and title.strip() else f"Grading Session - {question_paper_file.name}"
        has_file_rubric = bool(rubric_file)
        has_manual_rubric = bool(evaluation_criteria and evaluation_criteria.strip()) or bool(additional_instructions and additional_instructions.strip())

        if criteria_source == 'file':
            if not has_file_rubric:
                raise ValueError("Please upload a grading criteria document.")
            if has_manual_rubric:
                raise ValueError("Please use either a grading criteria document or manual grading criteria, not both.")
        elif criteria_source == 'manual':
            if has_file_rubric:
                raise ValueError("Please use either a grading criteria document or manual grading criteria, not both.")
            if not has_manual_rubric:
                raise ValueError("Please enter manual grading criteria.")
        else:
            if has_file_rubric and has_manual_rubric:
                raise ValueError("Please use either a grading criteria document or manual grading criteria, not both.")
            if not has_file_rubric and not has_manual_rubric:
                raise ValueError("Please provide grading criteria.")

        # Extract Question Paper Text
        qp_doc = self.doc_service.process_document(teacher, question_paper_file)
        qp_text = qp_doc.extracted_text.strip()
        if not qp_text:
            raise ValueError("Could not extract readable text from Question Paper document.")

        # Extract Master Answer Key (Optional)
        ma_text = None
        ma_name = "None"
        if master_answer_file:
            ma_doc = self.doc_service.process_document(teacher, master_answer_file)
            ma_text = ma_doc.extracted_text.strip()
            ma_name = ma_doc.original_filename

        # Extract Rubric / Criteria Text
        rubric_text = ""
        rubric_name = "None"
        if has_file_rubric:
            r_doc = self.doc_service.process_document(teacher, rubric_file)
            rubric_text = r_doc.extracted_text.strip()
            rubric_name = r_doc.original_filename
        elif has_manual_rubric:
            parts = []
            if evaluation_criteria and evaluation_criteria.strip():
                parts.append(f"Evaluation Criteria:\n{evaluation_criteria.strip()}")
            if additional_instructions and additional_instructions.strip():
                parts.append(f"Additional Instructions:\n{additional_instructions.strip()}")
            rubric_text = "\n\n".join(parts)
            rubric_name = "Manual Criteria"

        session = GradingSession.objects.create(
            teacher=teacher,
            title=title,
            status='READY',
            question_paper_name=qp_doc.original_filename,
            question_paper_text=qp_text,
            master_answer_name=ma_name,
            master_answer_text=ma_text,
            criteria_source=criteria_source,
            rubric_name=rubric_name,
            rubric_text=rubric_text,
            evaluation_criteria=evaluation_criteria,
            additional_instructions=additional_instructions,
            default_max_marks=default_max_marks
        )
        return session

    def grade_student_submission(self, submission_id: int, task_id: str = None) -> StudentGradingResult:
        """
        Evaluates a StudentSubmission using pre-extracted session context.
        Operates on persistent StudentSubmission database entity.
        """
        submission = StudentSubmission.objects.select_related('session', 'session__teacher').get(id=submission_id)
        session = submission.session
        teacher = session.teacher

        submission.status = 'PROCESSING'
        submission.task_id = task_id
        submission.started_at = timezone.now()
        submission.save(update_fields=['status', 'task_id', 'started_at'])

        try:
            # Step 1: Extract Student Answer Text
            if task_id:
                self.task_tracker.update_stage(task_id, 'EXTRACTING_HANDWRITING', f"Extracting text for '{submission.student_name}'...")

            if submission.answer_sheet_file:
                submission.answer_sheet_file.open('rb')
                student_doc = self.doc_service.process_document(teacher, submission.answer_sheet_file)
                student_text = student_doc.extracted_text.strip()
            else:
                raise GradingError("No answer sheet file found for submission.")

            if not student_text:
                raise GradingError("Could not extract readable text from student answer sheet.")

            submission.extracted_text = student_text
            submission.save(update_fields=['extracted_text'])

            # Step 2: Parse question blocks using session's pre-extracted texts
            question_blocks = self._parse_question_blocks(
                session.question_paper_text,
                session.master_answer_text,
                session.default_max_marks
            )

            if not question_blocks:
                question_blocks = [{
                    "question_number": "Q1",
                    "question_text": session.question_paper_text[:1000],
                    "master_answer": session.master_answer_text[:1000] if session.master_answer_text else None,
                    "max_marks": session.default_max_marks
                }]

            # Step 3: Evaluate question-by-question via LLM
            evaluated_scores = []
            for i, q_block in enumerate(question_blocks, 1):
                if task_id:
                    self.task_tracker.update_stage(
                        task_id,
                        'GENERATING',
                        f"Evaluating {q_block['question_number']} ({i}/{len(question_blocks)}) for '{submission.student_name}' via AI..."
                    )
                user_prompt, system_prompt = self.prompt_builder.build_grading_prompt(
                    question_number=q_block["question_number"],
                    question_text=q_block["question_text"],
                    master_answer=q_block["master_answer"],
                    criteria=session.rubric_text,
                    student_answer=student_text,
                    max_marks=q_block["max_marks"]
                )

                raw_response = self.llm_service.generate_text(prompt=user_prompt, system_prompt=system_prompt)
                eval_data = self._clean_and_parse_json(raw_response)
                validated_eval = self._validate_grading_schema(eval_data, q_block["question_number"], q_block["max_marks"])
                evaluated_scores.append(validated_eval)

            # Step 4: Atomically save StudentGradingResult and QuestionScore records
            if task_id:
                self.task_tracker.update_stage(task_id, 'FINALIZING', 'Saving evaluation results in PostgreSQL...')

            with transaction.atomic():
                total_score = sum(item["marks_awarded"] for item in evaluated_scores)
                max_score = sum(item["max_marks"] for item in evaluated_scores)
                overall_feedback = f"Graded {len(evaluated_scores)} questions. Total score: {total_score}/{max_score}."

                # Remove any stale result if retrying
                StudentGradingResult.objects.filter(submission=submission).delete()

                result = StudentGradingResult.objects.create(
                    submission=submission,
                    session=session,
                    student_name=submission.student_name,
                    answer_sheet_name=submission.answer_sheet_name,
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

                submission.status = 'COMPLETED'
                submission.progress = 100
                submission.current_stage = 'COMPLETED'
                submission.error_message = None
                submission.completed_at = timezone.now()
                submission.save()

            return result

        except Exception as e:
            err_msg = str(e)
            submission.status = 'FAILED'
            submission.error_message = err_msg
            submission.save(update_fields=['status', 'error_message'])
            if task_id:
                self.task_tracker.fail_task(task_id, err_msg)
            raise GradingError(err_msg)

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
        default_max_marks: float = 5.0,
        task_id: str = None
    ) -> StudentGradingResult:
        """Backward compatible helper creating session and evaluating single student."""
        session = self.create_grading_session(
            teacher=teacher,
            title=f"Grading Session - {student_name}",
            question_paper_file=question_paper_file,
            master_answer_file=master_answer_file,
            rubric_file=rubric_file,
            criteria_source='manual' if (evaluation_criteria or additional_instructions) else 'file',
            evaluation_criteria=evaluation_criteria,
            additional_instructions=additional_instructions,
            default_max_marks=default_max_marks
        )

        submission = StudentSubmission.objects.create(
            session=session,
            student_name=student_name.strip() if student_name else "Student",
            answer_sheet_name=getattr(student_answer_file, 'name', 'answer_sheet.pdf'),
            answer_sheet_file=student_answer_file,
            status='PENDING'
        )

        return self.grade_student_submission(submission.id, task_id=task_id)

    def _parse_question_blocks(self, qp_text: str, ma_text: str, default_max: float) -> List[Dict[str, Any]]:
        """Parses question numbers, text, master answers, and max marks from texts."""
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

            marks_match = re.search(r'[\(\[]\s*(\d+(?:\.\d+)?)\s*(?:marks?|pts?|m)?\s*[\)\]]', q_text_segment, re.IGNORECASE)
            parsed_max = float(marks_match.group(1)) if marks_match else default_max

            blocks.append({
                "question_number": q_num,
                "question_text": q_text_segment[:800],
                "master_answer": ma_text[:1000] if ma_text else None,
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
