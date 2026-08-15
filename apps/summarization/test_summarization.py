from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from apps.summarization.models import LectureSummary
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.signals import template_rendered
from django.test.client import store_rendered_templates

# Workaround for Django 5.0 template context copying on Python 3.14
template_rendered.disconnect(store_rendered_templates)

User = get_user_model()

class SummarizationTestCase(TestCase):
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

    def test_summary_create_and_download(self):
        # Create dummy file
        dummy_file = SimpleUploadedFile("lecture1.txt", b"This is some lecture material to summarize.")
        
        # Upload file for summarization
        response = self.client.post(reverse('summary_create'), {
            'source_file': dummy_file
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'summarization/review.html')
        
        # Verify db entry
        summary = LectureSummary.objects.get(source_file_name='lecture1.txt')
        self.assertIn("EXECUTIVE SUMMARY", summary.summary_text)
        self.assertTrue(summary.is_satisfactory)
        
        # Edit summary
        response = self.client.post(reverse('summary_review', kwargs={'summary_id': summary.id}), {
            'summary_text': 'Updated summary content',
            'is_satisfactory': 'false'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        summary.refresh_from_db()
        self.assertEqual(summary.summary_text, 'Updated summary content')
        self.assertFalse(summary.is_satisfactory)
        
        # Download PDF
        response = self.client.get(reverse('summary_download_pdf', kwargs={'summary_id': summary.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Download DOCX
        response = self.client.get(reverse('summary_download_docx', kwargs={'summary_id': summary.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
