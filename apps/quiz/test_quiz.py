from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from apps.quiz.models import Quiz, Question, QuestionOption
from apps.quiz.services import QuizService, QuizGenerationError
from django.test.signals import template_rendered
from django.test.client import store_rendered_templates

template_rendered.disconnect(store_rendered_templates)
User = get_user_model()

class QuizTestCase(TestCase):
    def setUp(self):
        import django.test.client
        def custom_store(store, signal, sender, template, context, **kwargs):
            store.setdefault("templates", []).append(template)
        django.test.client.store_rendered_templates = custom_store
        
        self.client = Client()
        self.teacher1 = User.objects.create_user(username='quiz_t1', password='password123', role=User.TEACHER)
        TeacherProfile.objects.create(user=self.teacher1, employee_id='EMP001', department='CS')
        
        self.teacher2 = User.objects.create_user(username='quiz_t2', password='password123', role=User.TEACHER)
        TeacherProfile.objects.create(user=self.teacher2, employee_id='EMP002', department='EE')

        self.client.login(username='quiz_t1', password='password123')

        self.mock_valid_json = (
            '{\n'
            '  "questions": [\n'
            '    {\n'
            '      "question": "What is mutual exclusion?",\n'
            '      "options": ["Exclusive access", "Shared access", "No access", "Preempted access"],\n'
            '      "correct_answer": "Exclusive access",\n'
            '      "explanation": "Mutual exclusion ensures one process at a time."\n'
            '    }\n'
            '  ]\n'
            '}'
        )

    @patch('apps.ai_engine.services.llm_service.LLMService.generate_text')
    def test_quiz_create_topic_only(self, mock_generate):
        mock_generate.return_value = self.mock_valid_json
        
        response = self.client.post(reverse('quiz_create'), {
            'topic': 'Operating Systems',
            'difficulty': 'EASY',
            'num_questions': 1
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/review.html')

        quiz = Quiz.objects.get(teacher=self.teacher1, topic='Operating Systems')
        self.assertEqual(quiz.num_questions, 1)
        self.assertEqual(quiz.questions.count(), 1)
        
        q = quiz.questions.first()
        self.assertEqual(q.text, "What is mutual exclusion?")
        self.assertEqual(q.options.count(), 4)
        correct_opt = q.options.get(is_correct=True)
        self.assertEqual(correct_opt.text, "Exclusive access")

    @patch('apps.ai_engine.services.llm_service.LLMService.generate_text')
    def test_quiz_create_file_only(self, mock_generate):
        mock_generate.return_value = self.mock_valid_json
        test_file = SimpleUploadedFile("os_notes.txt", b"Deadlock conditions: 1. Mutual Exclusion 2. Hold and Wait.", content_type="text/plain")

        response = self.client.post(reverse('quiz_create'), {
            'topic': '',
            'difficulty': 'MEDIUM',
            'num_questions': 1,
            'source_file': test_file
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/review.html')

        quiz = Quiz.objects.get(teacher=self.teacher1, source_file_name="os_notes.txt")
        self.assertIn("os_notes.txt", quiz.topic)

    def test_quiz_create_neither_topic_nor_file_returns_error(self):
        response = self.client.post(reverse('quiz_create'), {
            'topic': '',
            'difficulty': 'MEDIUM',
            'num_questions': 1
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/create.html')
        self.assertEqual(Quiz.objects.count(), 0)

    @patch('apps.ai_engine.services.llm_service.LLMService.generate_text')
    def test_invalid_json_shows_error(self, mock_generate):
        mock_generate.return_value = "This is not JSON text at all."

        response = self.client.post(reverse('quiz_create'), {
            'topic': 'Hardware',
            'difficulty': 'HARD',
            'num_questions': 1
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/create.html')
        self.assertEqual(Quiz.objects.count(), 0)

    @patch('apps.ai_engine.services.llm_service.LLMService.generate_text')
    def test_quiz_review_edit_and_accept(self, mock_generate):
        mock_generate.return_value = self.mock_valid_json
        quiz_service = QuizService()
        quiz = quiz_service.generate_quiz(self.teacher1, topic="Networking", difficulty="EASY", num_questions=1)

        question = quiz.questions.first()
        response = self.client.post(reverse('quiz_review', kwargs={'quiz_id': quiz.id}), {
            f"question_{question.id}": "Edited Question Text?",
            f"explanation_{question.id}": "Edited Explanation"
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        question.refresh_from_db()
        self.assertEqual(question.text, "Edited Question Text?")

        response = self.client.post(reverse('quiz_accept', kwargs={'quiz_id': quiz.id}), follow=True)
        self.assertEqual(response.status_code, 200)
        quiz.refresh_from_db()
        self.assertTrue(quiz.is_accepted)

    def test_teacher_isolation(self):
        # Create quiz for teacher2
        q2 = Quiz.objects.create(teacher=self.teacher2, topic="Private Quiz")
        # teacher1 attempts to review teacher2's quiz
        response = self.client.get(reverse('quiz_review', kwargs={'quiz_id': q2.id}))
        self.assertEqual(response.status_code, 404)
