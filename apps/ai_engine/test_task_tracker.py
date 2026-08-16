from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.ai_engine.task_tracker import TaskTracker, TaskState

User = get_user_model()

class TaskTrackerTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(username='t_tracker', password='password123', role=User.TEACHER)
        self.client.login(username='t_tracker', password='password123')
        self.tracker = TaskTracker()

    def test_create_and_get_task(self):
        task_id = self.tracker.create_task('quiz_generation', 'Generating Quiz')
        task = self.tracker.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task['status'], TaskState.RUNNING)
        self.assertEqual(task['task_type'], 'quiz_generation')
        self.assertEqual(task['progress'], 10)
        self.assertEqual(task['stage'], 'PREPARING')

    def test_update_stage_milestones(self):
        task_id = self.tracker.create_task('summarization', 'Summarizing Lecture Notes')
        
        # Advance stage to READING_DOCUMENT
        self.tracker.update_stage(task_id, 'READING_DOCUMENT')
        task = self.tracker.get_task(task_id)
        self.assertEqual(task['progress'], 30)
        self.assertEqual(task['stage'], 'READING_DOCUMENT')

        # Advance stage to GENERATING
        self.tracker.update_stage(task_id, 'GENERATING')
        task = self.tracker.get_task(task_id)
        self.assertEqual(task['progress'], 75)
        self.assertEqual(task['stage'], 'GENERATING')

    def test_complete_task(self):
        task_id = self.tracker.create_task('grading', 'Evaluating Sheet')
        self.tracker.complete_task(task_id, 'Grading complete!')
        task = self.tracker.get_task(task_id)
        self.assertEqual(task['status'], TaskState.COMPLETED)
        self.assertEqual(task['progress'], 100)
        self.assertEqual(task['message'], 'Grading complete!')

    def test_fail_task(self):
        task_id = self.tracker.create_task('quiz_generation', 'Generating Quiz')
        self.tracker.fail_task(task_id, 'Document parsing failed.')
        task = self.tracker.get_task(task_id)
        self.assertEqual(task['status'], TaskState.FAILED)
        self.assertEqual(task['error'], 'Document parsing failed.')

    def test_task_status_api_endpoint(self):
        task_id = self.tracker.create_task('quiz_generation', 'Generating Quiz')
        url = reverse('task_status_api', kwargs={'task_id': task_id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['task_id'], task_id)
        self.assertEqual(data['status'], TaskState.RUNNING)
        self.assertEqual(data['progress'], 10)

    def test_task_status_api_not_found(self):
        url = reverse('task_status_api', kwargs={'task_id': 'non-existent-task-id'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data['status'], TaskState.FAILED)
