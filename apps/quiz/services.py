import json
import logging
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
                # Check if FAISS index exists for teacher before rebuilding (FAISS Rebuilding Efficiency)
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
                # Combination 1: File Only -> Document-aware context (no fake filename semantic search!)
                formatted_context = f"SOURCE: {document.original_filename}\n{document.extracted_text[:4000]}"

        # Step 2: Build prompt
        user_prompt, system_prompt = self.prompt_builder.build_quiz_prompt(
            topic=topic_clean,
            difficulty=difficulty,
            num_questions=num_questions,
            formatted_context=formatted_context
        )

        # Step 3: LLM Generation
        raw_response = self.llm_service.generate_text(prompt=user_prompt, system_prompt=system_prompt)
        
        # Step 4: Parse & Validate JSON (NO MOCK FALLBACK)
        parsed_data = self._clean_and_parse_json(raw_response)
        validated_questions = self._validate_quiz_schema(parsed_data, num_questions)

        # Step 5: Save to Database
        with transaction.atomic():
            quiz_topic = topic_clean if topic_clean else f"Quiz from {source_file_name}"
            quiz = Quiz.objects.create(
                teacher=teacher,
                topic=quiz_topic,
                difficulty=difficulty,
                num_questions=len(validated_questions),
                source_file_name=source_file_name,
                is_accepted=False
            )

            for q_data in validated_questions:
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
            # Remove ```json or ``` at beginning and ``` at end
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

    def _validate_quiz_schema(self, data: Dict[str, Any], expected_count: int) -> List[Dict[str, Any]]:
        """Validates that parsed data matches MCQ schema rules strictly."""
        if not isinstance(data, dict) or "questions" not in data:
            raise QuizGenerationError("AI output missing top-level 'questions' list.")

        questions = data["questions"]
        if not isinstance(questions, list) or len(questions) == 0:
            raise QuizGenerationError("AI output returned an empty question list.")

        validated = []
        for idx, q in enumerate(questions, 1):
            if not isinstance(q, dict):
                raise QuizGenerationError(f"Question {idx} is invalid.")
            
            text = q.get("question")
            options = q.get("options")
            correct = q.get("correct_answer")

            if not text or not isinstance(text, str):
                raise QuizGenerationError(f"Question {idx} text is missing or invalid.")
            if not options or not isinstance(options, list) or len(options) != 4:
                raise QuizGenerationError(f"Question {idx} must have exactly 4 options.")
            if not correct or not isinstance(correct, str):
                raise QuizGenerationError(f"Question {idx} correct_answer is missing.")

            # Ensure correct answer matches one of the options
            clean_opts = [str(opt).strip() for opt in options]
            clean_correct = str(correct).strip()
            
            if not any(clean_correct.lower() == opt.lower() for opt in clean_opts):
                # Fallback: if correct answer is index or letter (A, B, C, D)
                match_found = False
                if clean_correct.upper() in ["A", "B", "C", "D"]:
                    opt_map = {"A": 0, "B": 1, "C": 2, "D": 3}
                    clean_correct = clean_opts[opt_map[clean_correct.upper()]]
                    match_found = True
                if not match_found:
                    raise QuizGenerationError(f"Question {idx} correct_answer ('{correct}') does not match any option.")

            validated.append({
                "question": str(text).strip(),
                "options": clean_opts,
                "correct_answer": clean_correct,
                "explanation": str(q.get("explanation", "")).strip()
            })

        return validated
