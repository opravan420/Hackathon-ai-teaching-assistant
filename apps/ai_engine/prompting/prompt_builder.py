from typing import Tuple, Optional

class PromptBuilder:
    """Manages system instructions and prompt construction for RAG and LLM tasks."""

    DEFAULT_SYSTEM_PROMPT = (
        "You are an AI Teaching Assistant for university faculty. "
        "Answer the user's question accurately using ONLY the provided course document context below.\n"
        "Rules:\n"
        "1. Base your answer strictly on the provided material.\n"
        "2. If the answer cannot be found or deduced from the provided context, clearly state that "
        "the information is not available in the provided material.\n"
        "3. Do not invent facts or external information not supported by the context.\n"
        "4. Keep your response clear, professional, and directly helpful to a teacher or student."
    )

    def build_rag_prompt(self, query: str, formatted_context: str, custom_system_prompt: Optional[str] = None) -> Tuple[str, str]:
        """Constructs system prompt and user prompt pair for generic RAG text generation."""
        system_prompt = custom_system_prompt or self.DEFAULT_SYSTEM_PROMPT
        user_prompt = (
            f"DOCUMENT CONTEXT:\n{formatted_context}\n\n"
            f"USER QUESTION:\n{query.strip()}"
        )
        return user_prompt, system_prompt

    def build_quiz_prompt(self, topic: str, difficulty: str, num_questions: int, formatted_context: str = "") -> Tuple[str, str]:
        """Constructs prompt for JSON Multiple Choice Question (MCQ) generation."""
        system_prompt = (
            "You are an expert academic quiz generator for university faculty.\n"
            "Generate high-quality multiple choice questions (MCQs) in raw JSON format.\n"
            "CRITICAL RULES:\n"
            "1. Output ONLY valid raw JSON containing a single top-level object with key 'questions'.\n"
            "2. Do NOT enclose in markdown code blocks like ```json ... ``` or add conversational commentary.\n"
            "3. Each item in 'questions' must have keys: 'question', 'options' (array of exactly 4 strings), "
            "'correct_answer' (must match one of the 4 options verbatim), and 'explanation'.\n"
            "4. Ensure options are distinct and plausible, with exactly one correct option.\n"
            "5. If document context is provided, questions MUST be based strictly on that context."
        )

        context_clause = ""
        if formatted_context.strip():
            context_clause = f"SOURCE DOCUMENT CONTEXT:\n{formatted_context.strip()}\n\n"

        topic_clause = f"TOPIC: {topic.strip()}\n" if topic.strip() else "TOPIC: Based on the provided source document content.\n"

        user_prompt = (
            f"{context_clause}"
            f"QUIZ GENERATION PARAMETERS:\n"
            f"{topic_clause}"
            f"DIFFICULTY LEVEL: {difficulty}\n"
            f"NUMBER OF QUESTIONS: {num_questions}\n\n"
            f"Return a raw JSON object formatted exactly as follows:\n"
            f'{{\n'
            f'  "questions": [\n'
            f'    {{\n'
            f'      "question": "Clear question text?",\n'
            f'      "options": ["Option A", "Option B", "Option C", "Option D"],\n'
            f'      "correct_answer": "Option A",\n'
            f'      "explanation": "Clear reason why Option A is correct."\n'
            f'    }}\n'
            f'  ]\n'
            f'}}'
        )
        return user_prompt, system_prompt

    def build_summary_prompt(self, formatted_context: str, custom_instruction: str = "") -> Tuple[str, str]:
        """Constructs prompt for lecture note summarization."""
        system_prompt = (
            "You are an academic summarization assistant for university faculty.\n"
            "Synthesize the provided course material into a clear, comprehensive, and well-structured lecture summary.\n"
            "Use clear section headers, bullet points, and key concept highlights.\n"
            "Do not invent external facts not supported by the document."
        )

        instruction_clause = f"TEACHER INSTRUCTION: {custom_instruction.strip()}\n\n" if custom_instruction.strip() else ""

        user_prompt = (
            f"{instruction_clause}"
            f"LECTURE DOCUMENT CONTENT:\n"
            f"{formatted_context.strip()}\n\n"
            f"Please generate the complete, structured lecture summary below:"
        )
        return user_prompt, system_prompt

    def build_grading_prompt(
        self,
        question_number: str,
        question_text: str,
        master_answer: str,
        criteria: str,
        student_answer: str,
        max_marks: float
    ) -> Tuple[str, str]:
        """Constructs prompt for question-by-question student short-answer evaluation."""
        system_prompt = (
            "You are an academic evaluation assistant for university faculty grading short-answer student responses.\n"
            "Evaluate the student's answer fairly and objectively against the reference answer key and grading criteria.\n"
            "CRITICAL RULES:\n"
            "1. Output ONLY valid raw JSON with keys: 'question_number', 'marks_awarded', 'max_marks', 'feedback'.\n"
            "2. Do NOT enclose in markdown code blocks or add text before/after JSON.\n"
            "3. 'marks_awarded' must be a numeric float between 0.0 and max_marks. Never award more than max_marks. Never give negative marks.\n"
            "4. Provide constructive feedback explaining score deductions or praising accurate responses."
        )

        user_prompt = (
            f"EVALUATION TASK FOR {question_number}:\n"
            f"QUESTION: {question_text.strip()}\n"
            f"MASTER REFERENCE ANSWER: {master_answer.strip()}\n"
            f"GRADING CRITERIA / RUBRIC: {criteria.strip() if criteria.strip() else 'Standard accuracy and technical correctness.'}\n"
            f"STUDENT ANSWER: {student_answer.strip()}\n"
            f"MAXIMUM MARKS AVAILABLE: {max_marks}\n\n"
            f"Return raw JSON matching this schema:\n"
            f'{{\n'
            f'  "question_number": "{question_number}",\n'
            f'  "marks_awarded": 4.5,\n'
            f'  "max_marks": {max_marks},\n'
            f'  "feedback": "Concise evaluation feedback explaining awarded marks."\n'
            f'}}'
        )
        return user_prompt, system_prompt
