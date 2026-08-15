from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from django.test.signals import template_rendered
from django.test.client import store_rendered_templates

# Workaround for Django 5.0 template context copying on Python 3.14
template_rendered.disconnect(store_rendered_templates)

User = get_user_model()

class AccountsTestCase(TestCase):
    def setUp(self):
        # Workaround for Django 5.0 template context copying on Python 3.14
        import django.test.client
        def custom_store(store, signal, sender, template, context, **kwargs):
            store.setdefault("templates", []).append(template)
        django.test.client.store_rendered_templates = custom_store
        self.client = Client()
        # Create a teacher user
        self.teacher_user = User.objects.create_user(
            username='teacher1',
            email='teacher1@school.edu',
            password='password123',
            role=User.TEACHER,
            first_name='John',
            last_name='Doe'
        )
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher_user,
            employee_id='EMP001',
            department='Computer Science'
        )

    def test_user_creation_and_roles(self):
        """Test user role assignment and string representation."""
        self.assertEqual(self.teacher_user.role, User.TEACHER)
        self.assertEqual(str(self.teacher_user), "teacher1 (TEACHER)")

    def test_teacher_profile_creation(self):
        """Test teacher profile fields and uniqueness."""
        self.assertEqual(self.teacher_user.teacher_profile.employee_id, 'EMP001')
        self.assertEqual(self.teacher_user.teacher_profile.department, 'Computer Science')
        self.assertEqual(str(self.teacher_profile), "John Doe (EMP001)")

    def test_login_logout_flows(self):
        """Test login redirect based on user role and logout flow."""
        # Test GET login
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

        # Test POST login as teacher
        response = self.client.post(reverse('login'), {
            'username': 'teacher1',
            'password': 'password123'
        }, follow=True)
        self.assertRedirects(response, reverse('teacher_dashboard'))
        self.assertEqual(response.status_code, 200)

        # Test GET profile view when logged in
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile.html')

        # Test logout
        response = self.client.get(reverse('logout'), follow=True)
        self.assertRedirects(response, reverse('login'))

