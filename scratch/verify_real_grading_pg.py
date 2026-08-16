import os
import sys
import django
from unittest.mock import patch

sys.path.insert(0, r'c:\Users\LENOVO\OneDrive\Desktop\Hackathon-ai-teaching-assistant')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.grading.services import GradingService
from apps.grading.models import GradingSession, StudentGradingResult, QuestionScore
from apps.ai_engine.task_tracker import TaskTracker

User = get_user_model()
teacher = User.objects.filter(role='TEACHER').first()
if not teacher:
    teacher = User.objects.create_user(username='teacher_verify', password='password123', role='TEACHER')

qp = SimpleUploadedFile('qp.txt', b"Q1 (5 Marks): What is an Operating System?", content_type="text/plain")
cr = SimpleUploadedFile('cr.txt', b"Grade based on process management definition.", content_type="text/plain")
st = SimpleUploadedFile('st.txt', b"An operating system manages computer hardware and software resources.", content_type="text/plain")

mock_json = '{"question_number": "Q1", "marks_awarded": 5.0, "max_marks": 5.0, "feedback": "Excellent definition."}'

print("Testing Answer Grading execution on PostgreSQL (ai_teaching_db)...")

with patch('apps.ai_engine.services.llm_service.LLMService.perform_health_check', return_value={'ollama_status': 'AVAILABLE', 'model_status': 'READY', 'model_tag': 'gemma3:4b', 'api_base': 'http://localhost:11434'}), \
     patch('apps.ai_engine.services.llm_service.LLMService.generate_text', return_value=mock_json):

    svc = GradingService()
    tracker = TaskTracker()
    task_id = tracker.create_task('grading', 'Real PostgreSQL Integration Test')

    res = svc.grade_student_sheet(
        teacher=teacher,
        question_paper_file=qp,
        student_answer_file=st,
        rubric_file=cr,
        student_name='PostgreSQL Test Student',
        default_max_marks=5.0,
        task_id=task_id
    )

    tracker.complete_task(task_id, 'Graded successfully!')

    # Verify records in PostgreSQL
    session_count = GradingSession.objects.filter(id=res.session.id).count()
    result_count = StudentGradingResult.objects.filter(id=res.id).count()
    score_count = QuestionScore.objects.filter(grading_result=res).count()

    print(f"[VERIFIED] GradingSession in PostgreSQL: {session_count} row(s)")
    print(f"[VERIFIED] StudentGradingResult in PostgreSQL: {result_count} row(s)")
    print(f"[VERIFIED] QuestionScore in PostgreSQL: {score_count} row(s)")
    print(f"[VERIFIED] TaskTracker status: {tracker.get_task(task_id)['status']} ({tracker.get_task(task_id)['progress']}%)")
    print(f"[VERIFIED] Total Score: {res.total_score}/{res.max_score}")
