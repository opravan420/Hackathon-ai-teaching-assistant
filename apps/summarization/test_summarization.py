from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from apps.summarization.models import LectureSummary
from django.test.signals import template_rendered
from django.test.client import store_rendered_templates

template_rendered.disconnect(store_rendered_templates)
User = get_user_model()

class SummarizationTestCase(TestCase):
    def setUp(self):
        import django.test.client
        def custom_store(store, signal, sender, template, context, **kwargs):
            store.setdefault("templates", []).append(template)
        django.test.client.store_rendered_templates = custom_store
        
        self.client = Client()
        self.teacher1 = User.objects.create_user(username='sum_t1', password='password123', role=User.TEACHER)
        TeacherProfile.objects.create(user=self.teacher1, employee_id='EMP001', department='CS')
        
        self.teacher2 = User.objects.create_user(username='sum_t2', password='password123', role=User.TEACHER)
        TeacherProfile.objects.create(user=self.teacher2, employee_id='EMP002', department='EE')

        self.client.login(username='sum_t1', password='password123')

    @patch('apps.ai_engine.services.llm_service.LLMService.generate_text')
    def test_summary_create_and_export(self, mock_generate):
        mock_generate.return_value = "# EXECUTIVE SUMMARY\n- Key Point 1\n- Key Point 2"
        dummy_file = SimpleUploadedFile("lecture1.txt", b"This is lecture material on process management.", content_type="text/plain")

        response = self.client.post(reverse('summary_create'), {
            'source_file': dummy_file,
            'custom_instruction': 'Summarize in simple terms'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'summarization/review.html')

        summary = LectureSummary.objects.get(teacher=self.teacher1, source_file_name='lecture1.txt')
        self.assertIn("EXECUTIVE SUMMARY", summary.summary_text)

        # Download PDF
        response = self.client.get(reverse('summary_download_pdf', kwargs={'summary_id': summary.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 100)

        # Download DOCX
        response = self.client.get(reverse('summary_download_docx', kwargs={'summary_id': summary.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertTrue(len(response.content) > 100)

    def test_teacher_isolation(self):
        s2 = LectureSummary.objects.create(teacher=self.teacher2, source_file_name="private.txt", summary_text="Secret")
        response = self.client.get(reverse('summary_review', kwargs={'summary_id': s2.id}))
        self.assertEqual(response.status_code, 404)
