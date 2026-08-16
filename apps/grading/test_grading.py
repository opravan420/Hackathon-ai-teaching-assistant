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
    def test_uploaded_rubric_with_optional_master_answer_key_success(self, mock_generate):
        mock_generate.return_value = self.mock_eval_json

        qp_file = SimpleUploadedFile("qp.txt", b"Q1 (5 Marks): What is deadlock?", content_type="text/plain")
        rubric_file = SimpleUploadedFile("rubric.txt", b"Grade based on process isolation and resource lock.", content_type="text/plain")
        student_file = SimpleUploadedFile("student_answer.txt", b"Deadlock happens when processes hold and wait.", content_type="text/plain")

        # Test WITHOUT master answer key (Master Answer Key is optional!)
        response = self.client.post(reverse('grading_create'), {
            'question_paper': qp_file,
            'criteria_source': 'file',
            'rubric': rubric_file,
            'student_name': 'Alice Smith',
            'student_image': student_file
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grading/review.html')

        session = GradingSession.objects.get(teacher=self.teacher1, question_paper_name='qp.txt')
        self.assertEqual(session.master_answer_name, 'None')
        self.assertEqual(session.rubric_name, 'rubric.txt')
        result = StudentGradingResult.objects.get(session=session, student_name='Alice Smith')
        self.assertEqual(result.total_score, 4.5)

    @patch('apps.ai_engine.services.llm_service.LLMService.generate_text')
    def test_manual_criteria_with_master_answer_key_success(self, mock_generate):
        mock_generate.return_value = self.mock_eval_json

        qp_file = SimpleUploadedFile("qp.txt", b"Q1 (5 Marks): What is deadlock?", content_type="text/plain")
        key_file = SimpleUploadedFile("key.txt", b"Q1: Deadlock is mutual waiting state.", content_type="text/plain")
        student_file = SimpleUploadedFile("student_answer.txt", b"Deadlock occurs when process wait on each other.", content_type="text/plain")

        response = self.client.post(reverse('grading_create'), {
            'question_paper': qp_file,
            'master_answer': key_file,
            'criteria_source': 'manual',
            'default_max_marks': '5.0',
            'evaluation_criteria': 'Check definition accuracy and key terms',
            'additional_instructions': 'Give partial credit for held resource concepts',
            'student_name': 'Bob Johnson',
            'student_image': student_file
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grading/review.html')

        session = GradingSession.objects.get(teacher=self.teacher1, question_paper_name='qp.txt')
        self.assertEqual(session.master_answer_name, 'key.txt')
        self.assertEqual(session.rubric_name, 'Manual Criteria')
        result = StudentGradingResult.objects.get(session=session, student_name='Bob Johnson')
        self.assertEqual(result.total_score, 4.5)

    def test_missing_criteria_validation_error(self):
        qp_file = SimpleUploadedFile("qp.txt", b"Q1: Define OS.", content_type="text/plain")
        student_file = SimpleUploadedFile("student.txt", b"Operating system manages hardware.", content_type="text/plain")

        # Submit without rubric document or manual criteria
        response = self.client.post(reverse('grading_create'), {
            'question_paper': qp_file,
            'criteria_source': 'file',
            'student_name': 'Charlie',
            'student_image': student_file
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grading/create.html')
        self.assertContains(response, "Please either upload a grading criteria document or enter the grading criteria manually.")

    def test_both_criteria_methods_validation_error(self):
        qp_file = SimpleUploadedFile("qp.txt", b"Q1: Define OS.", content_type="text/plain")
        rubric_file = SimpleUploadedFile("rubric.txt", b"Rubric text.", content_type="text/plain")
        student_file = SimpleUploadedFile("student.txt", b"Operating system manages hardware.", content_type="text/plain")

        # Submit with BOTH criteria document and manual criteria
        response = self.client.post(reverse('grading_create'), {
            'question_paper': qp_file,
            'criteria_source': 'manual',
            'rubric': rubric_file,
            'evaluation_criteria': 'Manual criteria text',
            'student_name': 'Charlie',
            'student_image': student_file
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grading/create.html')
        self.assertContains(response, "Please use either a grading criteria document or manual grading criteria, not both.")

    def test_teacher_isolation(self):
        s2 = GradingSession.objects.create(teacher=self.teacher2, question_paper_name="qp2.txt", master_answer_name="key2.txt")
        r2 = StudentGradingResult.objects.create(session=s2, student_name="Dave", answer_sheet_name="ans.txt", total_score=5, max_score=5)
        response = self.client.get(reverse('grading_result_review', kwargs={'result_id': r2.id}))
        self.assertEqual(response.status_code, 404)
