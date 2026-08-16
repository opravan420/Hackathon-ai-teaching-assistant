from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from apps.grading.models import GradingSession, StudentGradingResult, QuestionScore
from django.test.signals import template_rendered
from django.test.client import store_rendered_templates

template_rendered.disconnect(store_rendered_templates)
User = get_user_model()

class GradingTestCase(TestCase):
    def setUp(self):
        import django.test.client
        def custom_store(store, signal, sender, template, context, **kwargs):
            store.setdefault("templates", []).append(template)
        django.test.client.store_rendered_templates = custom_store
        
        self.client = Client()
        self.teacher1 = User.objects.create_user(username='grade_t1', password='password123', role=User.TEACHER)
        TeacherProfile.objects.create(user=self.teacher1, employee_id='EMP001', department='CS')
        
        self.teacher2 = User.objects.create_user(username='grade_t2', password='password123', role=User.TEACHER)
        TeacherProfile.objects.create(user=self.teacher2, employee_id='EMP002', department='EE')

        self.client.login(username='grade_t1', password='password123')

        self.mock_eval_json = (
            '{\n'
            '  "question_number": "Q1",\n'
            '  "marks_awarded": 4.5,\n'
            '  "max_marks": 5.0,\n'
            '  "feedback": "Correct definition of deadlock."\n'
            '}'
        )

    @patch('apps.ai_engine.services.llm_service.LLMService.generate_text')
    def test_text_based_student_grading_success(self, mock_generate):
        mock_generate.return_value = self.mock_eval_json

        qp_file = SimpleUploadedFile("qp.txt", b"Q1 (5 Marks): What is deadlock?", content_type="text/plain")
        key_file = SimpleUploadedFile("key.txt", b"Q1: Deadlock is a state where processes wait on each other.", content_type="text/plain")
        student_file = SimpleUploadedFile("student_answer.txt", b"Deadlock happens when processes hold and wait.", content_type="text/plain")

        response = self.client.post(reverse('grading_create'), {
            'question_paper': qp_file,
            'master_answer': key_file,
            'student_name': 'Alice Smith',
            'student_image': student_file
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grading/review.html')

        session = GradingSession.objects.get(teacher=self.teacher1, question_paper_name='qp.txt')
        result = StudentGradingResult.objects.get(session=session, student_name='Alice Smith')
        self.assertEqual(result.total_score, 4.5)
        self.assertEqual(result.max_score, 5.0)

        score = result.question_scores.first()
        self.assertEqual(score.score_given, 4.5)
        self.assertEqual(score.max_score, 5.0)

    def test_unsupported_image_answersheet_error_handling(self):
        qp_file = SimpleUploadedFile("qp.txt", b"Q1: Define OS.", content_type="text/plain")
        key_file = SimpleUploadedFile("key.txt", b"Q1: Operating System.", content_type="text/plain")
        image_file = SimpleUploadedFile("handwritten.png", b"Fake PNG Data", content_type="image/png")

        response = self.client.post(reverse('grading_create'), {
            'question_paper': qp_file,
            'master_answer': key_file,
            'student_name': 'Charlie',
            'student_image': image_file
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grading/create.html')
        self.assertContains(response, "An error occurred while grading the answers")

    def test_teacher_isolation(self):
        s2 = GradingSession.objects.create(teacher=self.teacher2, question_paper_name="qp2.txt", master_answer_name="key2.txt")
        r2 = StudentGradingResult.objects.create(session=s2, student_name="Dave", answer_sheet_name="ans.txt", total_score=5, max_score=5)
        response = self.client.get(reverse('grading_result_review', kwargs={'result_id': r2.id}))
        self.assertEqual(response.status_code, 404)
