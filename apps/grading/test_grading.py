import time
from unittest.mock import patch
from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from apps.grading.models import GradingSession, StudentSubmission, StudentGradingResult, QuestionScore
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

    @patch('apps.ai_engine.services.llm_service.LLMService.perform_health_check')
    def test_create_reusable_session_success(self, mock_health):
        mock_health.return_value = {"ollama_status": "AVAILABLE", "model_status": "READY", "model_tag": "gemma3:4b", "api_base": "http://localhost:11434"}

        qp_file = SimpleUploadedFile("qp.txt", b"Q1 (5 Marks): What is deadlock?", content_type="text/plain")
        rubric_file = SimpleUploadedFile("rubric.txt", b"Grade based on process isolation and resource lock.", content_type="text/plain")

        response = self.client.post(reverse('grading_create'), {
            'title': 'OS Midterm 2026',
            'question_paper': qp_file,
            'criteria_source': 'file',
            'rubric': rubric_file,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grading/session_detail.html')

        session = GradingSession.objects.get(teacher=self.teacher1, title='OS Midterm 2026')
        self.assertEqual(session.status, 'READY')
        self.assertEqual(session.question_paper_name, 'qp.txt')
        self.assertEqual(session.rubric_name, 'rubric.txt')
        self.assertIn("deadlock", session.question_paper_text.lower())

    def test_missing_criteria_validation_error(self):
        qp_file = SimpleUploadedFile("qp.txt", b"Q1: Define OS.", content_type="text/plain")

        response = self.client.post(reverse('grading_create'), {
            'title': 'Missing Criteria Session',
            'question_paper': qp_file,
            'criteria_source': 'file',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grading/create.html')
        self.assertContains(response, "Please upload a grading criteria document.")

    def test_both_criteria_methods_validation_error(self):
        qp_file = SimpleUploadedFile("qp.txt", b"Q1: Define OS.", content_type="text/plain")
        rubric_file = SimpleUploadedFile("rubric.txt", b"Rubric text.", content_type="text/plain")

        response = self.client.post(reverse('grading_create'), {
            'title': 'Both Criteria Session',
            'question_paper': qp_file,
            'criteria_source': 'manual',
            'rubric': rubric_file,
            'evaluation_criteria': 'Manual criteria text',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grading/create.html')
        self.assertContains(response, "Please use either a grading criteria document or manual grading criteria, not both.")

    def test_teacher_isolation(self):
        s2 = GradingSession.objects.create(
            teacher=self.teacher2,
            title="Teacher 2 Session",
            question_paper_name="qp2.txt",
            question_paper_text="Q1: Define process."
        )
        response = self.client.get(reverse('grading_session_detail', kwargs={'session_id': s2.id}))
        self.assertEqual(response.status_code, 404)


class AsyncGradingSessionTestCase(TransactionTestCase):
    def setUp(self):
        self.client = Client()
        self.teacher1 = User.objects.create_user(username='async_session_t1', password='password123', role=User.TEACHER)
        TeacherProfile.objects.create(user=self.teacher1, employee_id='EMP003', department='CS')
        self.client.login(username='async_session_t1', password='password123')

        self.session = GradingSession.objects.create(
            teacher=self.teacher1,
            title="Async OS Exam 2026",
            status="READY",
            question_paper_name="qp.txt",
            question_paper_text="Q1 (5 Marks): What is an Operating System?",
            rubric_name="rubric.txt",
            rubric_text="Grade based on resource management accuracy."
        )

        self.mock_eval_json = (
            '{\n'
            '  "question_number": "Q1",\n'
            '  "marks_awarded": 5.0,\n'
            '  "max_marks": 5.0,\n'
            '  "feedback": "Excellent definition of hardware management."\n'
            '}'
        )

    @patch('apps.ai_engine.services.llm_service.LLMService.perform_health_check')
    @patch('apps.ai_engine.services.llm_service.LLMService.generate_text')
    def test_grade_multiple_students_under_same_session(self, mock_generate, mock_health):
        mock_health.return_value = {"ollama_status": "AVAILABLE", "model_status": "READY", "model_tag": "gemma3:4b", "api_base": "http://localhost:11434"}
        mock_generate.return_value = self.mock_eval_json

        student1_file = SimpleUploadedFile("alice.txt", b"An OS manages computer hardware and software.", content_type="text/plain")
        student2_file = SimpleUploadedFile("bob.txt", b"An OS acts as an intermediary between user and computer.", content_type="text/plain")

        # Submit Student 1 (Alice)
        resp1 = self.client.post(
            reverse('grade_student_ajax', kwargs={'session_id': self.session.id}),
            {
                'student_name': 'Alice Smith',
                'student_image': student1_file
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertEqual(data1['status'], 'STARTED')

        # Wait for Student 1 completion
        from apps.ai_engine.task_tracker import TaskTracker
        tracker = TaskTracker()
        for _ in range(25):
            task = tracker.get_task(data1['task_id'])
            if task and task['status'] in ('COMPLETED', 'FAILED'):
                break
            time.sleep(0.2)

        # Submit Student 2 (Bob) under the SAME session
        resp2 = self.client.post(
            reverse('grade_student_ajax', kwargs={'session_id': self.session.id}),
            {
                'student_name': 'Bob Jones',
                'student_image': student2_file
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2['status'], 'STARTED')

        for _ in range(25):
            task = tracker.get_task(data2['task_id'])
            if task and task['status'] in ('COMPLETED', 'FAILED'):
                break
            time.sleep(0.2)

        # Verify PostgreSQL database state: Both students linked to same session!
        submissions = StudentSubmission.objects.filter(session=self.session)
        self.assertEqual(submissions.count(), 2)

        results = StudentGradingResult.objects.filter(session=self.session)
        self.assertEqual(results.count(), 2)
        self.assertTrue(results.filter(student_name='Alice Smith').exists())
        self.assertTrue(results.filter(student_name='Bob Jones').exists())
