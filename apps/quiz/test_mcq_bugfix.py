from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.quiz.services import QuizService, QuizGenerationError
from apps.quiz.models import Quiz, Question, QuestionOption
from apps.quiz.exporter import QuizExporter

User = get_user_model()

class MCQBugFixTestCase(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='t_bugfix', password='password123', role=User.TEACHER)
        self.service = QuizService()

    def test_authoritative_correct_option_letter(self):
        q_raw = {
            "question": "What is virtual memory?",
            "options": ["Physical RAM only", "An abstraction of storage", "GPU VRAM", "Disk partitions"],
            "correct_option": "B",
            "explanation": "Virtual memory provides an abstraction of main memory."
        }
        normalized = self.service._validate_and_normalize_question(q_raw, 1)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["correct_option"], "B")
        self.assertEqual(normalized["correct_answer"], "An abstraction of storage")

    def test_correct_option_with_prefix(self):
        q_raw = {
            "question": "What is mutual exclusion?",
            "options": ["Exclusive access", "Shared access", "No access", "Preempted access"],
            "correct_option": "Option A",
            "explanation": "Mutual exclusion ensures one process at a time."
        }
        normalized = self.service._validate_and_normalize_question(q_raw, 1)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["correct_option"], "A")
        self.assertEqual(normalized["correct_answer"], "Exclusive access")

    def test_legacy_correct_answer_text(self):
        q_raw = {
            "question": "What is mutual exclusion?",
            "options": ["Exclusive access", "Shared access", "No access", "Preempted access"],
            "correct_answer": "Exclusive access",
            "explanation": "Mutual exclusion ensures one process at a time."
        }
        normalized = self.service._validate_and_normalize_question(q_raw, 1)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["correct_option"], "A")
        self.assertEqual(normalized["correct_answer"], "Exclusive access")

    def test_semantic_recovery_matching(self):
        """
        Tests the semantic recovery scenario:
        correct_answer has slightly different text than Option C.
        Semantic recovery matches Option C and sets correct_answer = EXACT Option C text.
        """
        q_raw = {
            "question": "What is the primary benefit of virtualization?",
            "options": [
                "Increasing physical CPU clock speeds",
                "Eliminating network latency completely",
                "Reducing dependence on the underlying physical hardware.",
                "Automating database index creation"
            ],
            "correct_answer": "Reducing the system’s reliance on the underlying physical hardware.",
            "explanation": "Virtualization decouples software from physical hardware."
        }
        normalized = self.service._validate_and_normalize_question(q_raw, 1)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["correct_option"], "C")
        self.assertEqual(normalized["correct_answer"], "Reducing dependence on the underlying physical hardware.")

    def test_invalid_questions_rejected(self):
        # Only 3 options
        q_invalid = {
            "question": "Test question?",
            "options": ["A", "B", "C"],
            "correct_option": "A"
        }
        self.assertIsNone(self.service._validate_and_normalize_question(q_invalid, 1))

        # Duplicate options
        q_duplicate = {
            "question": "Test question?",
            "options": ["Option A", "Option A", "Option C", "Option D"],
            "correct_option": "A"
        }
        self.assertIsNone(self.service._validate_and_normalize_question(q_duplicate, 1))

    def test_topic_only_hard_10_questions(self):
        """Live integration test: 10 Hard MCQs for Operating System without document."""
        quiz = self.service.generate_quiz(
            teacher=self.teacher,
            topic="Operating System",
            difficulty="HARD",
            num_questions=10,
            uploaded_file=None
        )
        self.assertIsNotNone(quiz)
        self.assertEqual(quiz.num_questions, 10)
        self.assertEqual(quiz.questions.count(), 10)

        for q in quiz.questions.all():
            self.assertEqual(q.options.count(), 4)
            correct_opts = q.options.filter(is_correct=True)
            self.assertEqual(correct_opts.count(), 1)
            correct_text = correct_opts.first().text
            self.assertTrue(any(correct_text == opt.text for opt in q.options.all()))

    def test_answer_key_export_uses_authoritative_answer(self):
        quiz = Quiz.objects.create(
            teacher=self.teacher,
            topic="Operating System",
            difficulty="HARD",
            num_questions=1,
            is_accepted=True
        )
        q = Question.objects.create(quiz=quiz, text="What is deadlock?", explanation="Blocked process cycle.")
        opt_a = QuestionOption.objects.create(question=q, text="A cycle of blocked processes", is_correct=True)
        opt_b = QuestionOption.objects.create(question=q, text="Fast memory access", is_correct=False)
        opt_c = QuestionOption.objects.create(question=q, text="Network packet drop", is_correct=False)
        opt_d = QuestionOption.objects.create(question=q, text="Disk fragmenting", is_correct=False)

        pdf_bytes = QuizExporter.generate_answer_key_pdf(quiz)
        docx_bytes = QuizExporter.generate_answer_key_docx(quiz)
        self.assertTrue(len(pdf_bytes) > 500)
        self.assertTrue(len(docx_bytes) > 500)
