from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from apps.grading.models import GradingSession, StudentGradingResult, QuestionScore
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.signals import template_rendered
from django.test.client import store_rendered_templates

# Workaround for Django 5.0 template context copying on Python 3.14
template_rendered.disconnect(store_rendered_templates)

User = get_user_model()

class GradingTestCase(TestCase):
    def setUp(self):
        # Workaround for Django 5.0 template context copying on Python 3.14
        import django.test.client
        def custom_store(store, signal, sender, template, context, **kwargs):
            store.setdefault("templates", []).append(template)
        django.test.client.store_rendered_templates = custom_store
        self.client = Client()
        
        # Create Teacher
        self.teacher_user = User.objects.create_user(
            username='teacher1', password='password123', role=User.TEACHER
        )
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher_user, employee_id='EMP001', department='CS'
        )
        
        # Log in
        self.client.login(username='teacher1', password='password123')

    def test_grading_create_and_review(self):
        # Create mock file uploads
        qp_file = SimpleUploadedFile("question_paper.pdf", b"QP content")
        key_file = SimpleUploadedFile("answer_key.docx", b"Key content")
        rubric_file = SimpleUploadedFile("rubric.txt", b"Rubric content")
        student_sheet = SimpleUploadedFile("student_answers.png", b"PNG image data", content_type="image/png")
        
        # Post files
        response = self.client.post(reverse('grading_create'), {
            'question_paper': qp_file,
            'master_answer': key_file,
            'rubric': rubric_file,
            'student_name': 'Bob Miller',
            'student_image': student_sheet
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grading/review.html')
        
        # Verify db entities
        session = GradingSession.objects.get(question_paper_name='question_paper.pdf')
        result = StudentGradingResult.objects.get(student_name='Bob Miller', session=session)
        self.assertEqual(result.max_score, 15.0)
        self.assertEqual(result.total_score, 12.0)
        
        scores = result.question_scores.all().order_by('question_number')
        self.assertEqual(scores.count(), 3)
        self.assertEqual(scores[0].question_number, "Q1")
        self.assertEqual(scores[0].score_given, 5.0)
        
        # Modify score
        q1_score = scores[0]
        response = self.client.post(reverse('grading_result_review', kwargs={'result_id': result.id}), {
            f"score_{q1_score.id}": "4.0",
            f"comment_{q1_score.id}": "Adjusted score feedback",
            "overall_feedback": "Adjusted overall feedback"
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        q1_score.refresh_from_db()
        self.assertEqual(q1_score.score_given, 4.0)
        self.assertEqual(q1_score.feedback, "Adjusted score feedback")
        
        result.refresh_from_db()
        # Q1 went from 5.0 to 4.0. So total score should be 12.0 - 1.0 = 11.0
        self.assertEqual(result.total_score, 11.0)
        self.assertEqual(result.overall_feedback, "Adjusted overall feedback")
