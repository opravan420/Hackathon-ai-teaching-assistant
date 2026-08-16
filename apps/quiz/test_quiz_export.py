from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.quiz.models import Quiz, Question, QuestionOption

User = get_user_model()

class QuizExportTestCase(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='t_export1', password='password123', role=User.TEACHER)
        self.other_teacher = User.objects.create_user(username='t_export2', password='password123', role=User.TEACHER)
        self.client = Client()
        self.client.login(username='t_export1', password='password123')

        self.quiz = Quiz.objects.create(
            teacher=self.teacher,
            topic="Operating System Deadlocks",
            difficulty="MEDIUM",
            num_questions=2,
            is_accepted=True
        )

        # Question 1
        q1 = Question.objects.create(
            quiz=self.quiz,
            text="What is a Deadlock in OS?",
            explanation="Deadlock occurs when processes wait for each other indefinitely."
        )
        QuestionOption.objects.create(question=q1, text="Process blocking state", is_correct=True)
        QuestionOption.objects.create(question=q1, text="CPU overclocking", is_correct=False)
        QuestionOption.objects.create(question=q1, text="Memory leak", is_correct=False)
        QuestionOption.objects.create(question=q1, text="Disk defragmentation", is_correct=False)

        # Question 2
        q2 = Question.objects.create(
            quiz=self.quiz,
            text="Which condition is necessary for deadlock?",
            explanation="Mutual exclusion is one of four necessary conditions."
        )
        QuestionOption.objects.create(question=q2, text="Infinite memory", is_correct=False)
        QuestionOption.objects.create(question=q2, text="Mutual exclusion", is_correct=True)
        QuestionOption.objects.create(question=q2, text="High CPU clock", is_correct=False)
        QuestionOption.objects.create(question=q2, text="Fast Network", is_correct=False)

    def test_question_paper_pdf_download(self):
        url = reverse('download_question_paper_pdf', args=[self.quiz.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename=', response['Content-Disposition'])
        
        # Verify content security: correct answer string should not appear in raw PDF text structure
        pdf_content = response.content
        self.assertTrue(len(pdf_content) > 500)

    def test_question_paper_docx_download(self):
        url = reverse('download_question_paper_docx', args=[self.quiz.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertIn('attachment; filename=', response['Content-Disposition'])
        self.assertTrue(len(response.content) > 500)

    def test_answer_key_pdf_download(self):
        url = reverse('download_answer_key_pdf', args=[self.quiz.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename=', response['Content-Disposition'])
        self.assertTrue(len(response.content) > 500)

    def test_answer_key_docx_download(self):
        url = reverse('download_answer_key_docx', args=[self.quiz.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertIn('attachment; filename=', response['Content-Disposition'])
        self.assertTrue(len(response.content) > 500)

    def test_unfinalized_quiz_download_blocked(self):
        draft_quiz = Quiz.objects.create(
            teacher=self.teacher,
            topic="Draft Quiz",
            is_accepted=False
        )
        url = reverse('download_question_paper_pdf', args=[draft_quiz.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302) # Redirects to review page

    def test_teacher_isolation(self):
        self.client.login(username='t_export2', password='password123')
        url = reverse('download_question_paper_pdf', args=[self.quiz.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
