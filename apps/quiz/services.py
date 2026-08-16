import json
import logging
import difflib
import re
from typing import Optional, Dict, Any, List
from django.db import transaction

from apps.quiz.models import Quiz, Question, QuestionOption
from apps.ai_engine.document_processing.service import DocumentService
from apps.ai_engine.rag.vector_store import VectorStoreManager
from apps.ai_engine.rag.retrieval_service import RetrievalService
from apps.ai_engine.prompting.context_builder import ContextBuilder
from apps.ai_engine.prompting.prompt_builder import PromptBuilder
from apps.ai_engine.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class QuizGenerationError(Exception):
    """Raised when quiz generation fails due to invalid LLM output or missing context."""
    pass

class QuizService:
    """Core service for AI Quiz Generation."""

    MAX_QUESTION_RETRIES = 3

    def __init__(self):
        self.doc_service = DocumentService()
        self.vector_manager = VectorStoreManager()
        self.retrieval_service = RetrievalService()
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.llm_service = LLMService()

    def generate_quiz(
        self,
        teacher,
        topic: str,
        difficulty: str,
        num_questions: int,
        uploaded_file = None
    ) -> Quiz:
        """
        Generates a Quiz using Gemma and optional RAG context.
        Validates input combinations:
        - File Only: Document-aware text extraction (no fake topic query)
        - Topic Only: General knowledge generation
        - Both File + Topic: RAG retrieval matching topic query against document
        - Neither: Raises ValueError
        """
        topic_clean = topic.strip() if topic else ""
        
        if not topic_clean and not uploaded_file:
            raise ValueError("Please provide at least a Topic or a Source File to generate a quiz.")

        formatted_context = ""
        source_file_name = None

        if uploaded_file:
            # Step 1: Extract document text
            document = self.doc_service.process_document(teacher, uploaded_file)
            source_file_name = document.original_filename

            if topic_clean:
                # Combination 3: Both File + Topic -> RAG Semantic Search
                if not self.vector_manager.has_index(teacher.id):
                    self.retrieval_service.rebuild_index_for_teacher(teacher.id)
                
                top_k = max(num_questions * 2, 5)
                retrieved_chunks = self.retrieval_service.retrieve_relevant_context(
                    query=topic_clean,
                    teacher_id=teacher.id,
                    top_k=top_k
                )
                if retrieved_chunks:
                    formatted_context = self.context_builder.build_context(retrieved_chunks)
                else:
                    # Fall back to sampled document text if RAG yielded no chunks
                    formatted_context = f"SOURCE: {document.original_filename}\n{document.extracted_text[:4000]}"
            else:
                # Combination 1: File Only -> Document-aware context
                formatted_context = f"SOURCE: {document.original_filename}\n{document.extracted_text[:4000]}"

        # Step 2: LLM Generation & Per-Question Validation Loop
        valid_questions = []

        user_prompt, system_prompt = self.prompt_builder.build_quiz_prompt(
            topic=topic_clean,
            difficulty=difficulty,
            num_questions=num_questions,
            formatted_context=formatted_context
        )

        raw_response = self.llm_service.generate_text(prompt=user_prompt, system_prompt=system_prompt)
        parsed_data = self._clean_and_parse_json(raw_response)

        raw_list = parsed_data.get("questions", []) if isinstance(parsed_data, dict) else []
        for idx, q_item in enumerate(raw_list, 1):
            norm_q = self._validate_and_normalize_question(q_item, idx)
            if norm_q:
                valid_questions.append(norm_q)

        # Step 3: Per-Question Retry Loop if we have fewer valid questions than requested
        retry_count = 0
        while len(valid_questions) < num_questions and retry_count < self.MAX_QUESTION_RETRIES:
            retry_count += 1
            needed = num_questions - len(valid_questions)
            logger.info(f"Quiz generation: Got {len(valid_questions)}/{num_questions} valid questions. Retrying for {needed} missing questions (attempt {retry_count}/{self.MAX_QUESTION_RETRIES})...")
            
            retry_user_prompt, retry_sys_prompt = self.prompt_builder.build_quiz_prompt(
                topic=topic_clean,
                difficulty=difficulty,
                num_questions=needed,
                formatted_context=formatted_context
            )
            try:
                retry_raw = self.llm_service.generate_text(prompt=retry_user_prompt, system_prompt=retry_sys_prompt)
                retry_data = self._clean_and_parse_json(retry_raw)
                retry_list = retry_data.get("questions", []) if isinstance(retry_data, dict) else []
                for idx, q_item in enumerate(retry_list, len(valid_questions) + 1):
                    norm_q = self._validate_and_normalize_question(q_item, idx)
                    if norm_q:
                        valid_questions.append(norm_q)
                        if len(valid_questions) >= num_questions:
                            break
            except Exception as e:
                logger.warning(f"Retry attempt {retry_count} failed: {e}")

        if not valid_questions:
            raise QuizGenerationError("AI failed to generate valid structured MCQs. Please try again.")

        # Cap to requested num_questions
        valid_questions = valid_questions[:num_questions]

        # Step 4: Save to Database
        with transaction.atomic():
            quiz_topic = topic_clean if topic_clean else f"Quiz from {source_file_name}"
            quiz = Quiz.objects.create(
                teacher=teacher,
                topic=quiz_topic,
                difficulty=difficulty,
                num_questions=len(valid_questions),
                source_file_name=source_file_name,
                is_accepted=False
            )

            for q_data in valid_questions:
                q_obj = Question.objects.create(
                    quiz=quiz,
                    text=q_data['question'],
                    explanation=q_data.get('explanation', '')
                )
                for opt_text in q_data['options']:
                    is_corr = (opt_text.strip().lower() == q_data['correct_answer'].strip().lower())
                    QuestionOption.objects.create(
                        question=q_obj,
                        text=opt_text.strip(),
                        is_correct=is_corr
                    )

        return quiz

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
            logger.error(f"Failed to parse LLM quiz JSON response: {e}\nRaw output: {response_text[:300]}")
            raise QuizGenerationError("AI response was not valid structured JSON. Please try again.")

    def _validate_and_normalize_question(self, q: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
        """
        Validates and normalizes an individual MCQ data block immediately after parsing.
        
        Canonical Invariants:
        1. options is an array of exactly 4 non-empty, distinct option strings.
        2. correct_option is in {'A', 'B', 'C', 'D'}.
        3. correct_answer MUST ALWAYS equal the exact text of the selected option (derived).
        """
        if not isinstance(q, dict):
            logger.debug(f"Question [{idx}] is not a dict: {q}")
            return None

        text = q.get("question")
        raw_options = q.get("options")
        if not text or not isinstance(text, str) or not text.strip():
            logger.debug(f"Question [{idx}] has missing or empty question text.")
            return None

        # Extract exactly 4 clean options (supports list of strings or list of dicts)
        clean_opts = []
        if isinstance(raw_options, list):
            for item in raw_options:
                if isinstance(item, str):
                    t = item.strip()
                    if t:
                        clean_opts.append(t)
                elif isinstance(item, dict):
                    t = str(item.get("text") or item.get("option") or item.get("val") or "").strip()
                    if t:
                        clean_opts.append(t)

        if len(clean_opts) != 4:
            logger.debug(f"Question [{idx}] does not have 4 options: {clean_opts}")
            return None

        # Ensure all 4 options are distinct (case-insensitive)
        lower_opts = [o.lower() for o in clean_opts]
        if len(set(lower_opts)) != 4:
            logger.debug(f"Question [{idx}] options are not distinct: {clean_opts}")
            return None

        target_idx = None

        # Gather any potential raw answer indicator from the LLM JSON
        raw_opt_val = q.get("correct_option") or q.get("correct_answer_index")
        raw_ans_val = q.get("correct_answer") or q.get("answer")

        # Combine candidates for inspection
        candidates = [c for c in [raw_opt_val, raw_ans_val] if c is not None]

        # STAGE 1: Letter / Index Extraction (A, B, C, D or 0, 1, 2, 3)
        for cand in candidates:
            cand_str = str(cand).strip()
            if not cand_str:
                continue

            # Case A1: Exact match "A", "B", "C", "D" or "0", "1", "2", "3"
            cand_upper = cand_str.upper()
            letter_map = {"A": 0, "B": 1, "C": 2, "D": 3, "0": 0, "1": 1, "2": 2, "3": 3, "4": 3}
            if cand_upper in letter_map:
                target_idx = letter_map[cand_upper]
                break

            # Case A2: Substring or prefix match e.g. "Option A", "A.", "(A)", "Option 1", "A: ..."
            m_letter = re.search(r'\b(OPTION|CHOICE)?\s*([A-D])\b', cand_upper)
            if m_letter:
                letter_found = m_letter.group(2)
                target_idx = {"A": 0, "B": 1, "C": 2, "D": 3}[letter_found]
                break

            m_num = re.search(r'\b(OPTION|CHOICE)?\s*([1-4])\b', cand_upper)
            if m_num:
                num_found = int(m_num.group(2)) - 1
                target_idx = num_found
                break

        # STAGE 2: Exact / Case-insensitive text match against clean_opts
        if target_idx is None:
            for cand in candidates:
                cand_str = str(cand).strip().lower()
                if not cand_str:
                    continue
                for i, opt in enumerate(clean_opts):
                    if opt.lower() == cand_str:
                        target_idx = i
                        break
                if target_idx is not None:
                    break

        # STAGE 3: Controlled Semantic Recovery Match (difflib ratio)
        if target_idx is None:
            for cand in candidates:
                cand_str = str(cand).strip().lower()
                if len(cand_str) >= 5:
                    scores = []
                    for i, opt in enumerate(clean_opts):
                        ratio = difflib.SequenceMatcher(None, cand_str, opt.lower()).ratio()
                        scores.append((ratio, i))
                    
                    scores.sort(key=lambda x: x[0], reverse=True)
                    best_score, best_i = scores[0]
                    second_score = scores[1][0]

                    if best_score >= 0.55 and (best_score - second_score) >= 0.12:
                        target_idx = best_i
                        logger.info(f"Question [{idx}]: Semantic match recovered correct_option -> {['A','B','C','D'][best_i]} (score: {best_score:.2f})")
                        break

        if target_idx is None or target_idx < 0 or target_idx > 3:
            logger.warning(f"Question [{idx}]: Failed to determine valid correct option from candidates: {candidates}")
            return None

        # DERIVE CANONICAL REPRESENTATION (EXACT MATCH GUARANTEED BY DESIGN)
        correct_option_letter = ["A", "B", "C", "D"][target_idx]
        derived_correct_answer = clean_opts[target_idx]

        normalized_item = {
            "question": str(text).strip(),
            "options": clean_opts,
            "structured_options": [
                {"id": "A", "text": clean_opts[0]},
                {"id": "B", "text": clean_opts[1]},
                {"id": "C", "text": clean_opts[2]},
                {"id": "D", "text": clean_opts[3]},
            ],
            "correct_option": correct_option_letter,
            "correct_answer": derived_correct_answer, # Derivation invariant satisfied!
            "explanation": str(q.get("explanation", "")).strip()
        }

        logger.debug(f"RAW QUESTION [{idx}]: {q}")
        logger.debug(f"NORMALIZED QUESTION [{idx}]: {normalized_item}")

        return normalized_item
