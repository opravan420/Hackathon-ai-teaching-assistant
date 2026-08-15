from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from apps.quiz.models import Quiz, Question, QuestionOption
from django.test.signals import template_rendered
from django.test.client import store_rendered_templates

# Workaround for Django 5.0 template context copying on Python 3.14
template_rendered.disconnect(store_rendered_templates)

User = get_user_model()

class QuizTestCase(TestCase):
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

    def test_quiz_create_and_review(self):
        # Generate quiz
        response = self.client.post(reverse('quiz_create'), {
            'topic': 'Operating Systems',
            'difficulty': 'MEDIUM',
            'num_questions': 3
        }, follow=True)
        
        # Verify redirect to review page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/review.html')
        
        # Verify database entities
        quiz = Quiz.objects.get(topic='Operating Systems')
        self.assertEqual(quiz.num_questions, 3)
        self.assertEqual(quiz.questions.count(), 3)
        self.assertFalse(quiz.is_accepted)
        
        # Edit question
        question = quiz.questions.first()
        response = self.client.post(reverse('quiz_review', kwargs={'quiz_id': quiz.id}), {
            f"question_{question.id}": "Updated Question Text"
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        question.refresh_from_db()
        self.assertEqual(question.text, "Updated Question Text")
        
        # Accept quiz
        response = self.client.post(reverse('quiz_accept', kwargs={'quiz_id': quiz.id}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/dashboard.html')
        quiz.refresh_from_db()
        self.assertTrue(quiz.is_accepted)
