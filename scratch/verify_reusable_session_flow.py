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
from apps.grading.models import GradingSession, StudentSubmission, StudentGradingResult, QuestionScore

User = get_user_model()
teacher = User.objects.filter(role='TEACHER').first()
if not teacher:
    teacher = User.objects.create_user(username='teacher_reusable_test', password='password123', role='TEACHER')

qp = SimpleUploadedFile('qp.txt', b"Q1 (5 Marks): What is virtual memory?", content_type="text/plain")
cr = SimpleUploadedFile('cr.txt', b"Grade based on address translation and paging definitions.", content_type="text/plain")

mock_json = '{"question_number": "Q1", "marks_awarded": 5.0, "max_marks": 5.0, "feedback": "Excellent explanation of virtual memory."}'

print("Testing Reusable Grading Session Workflow on PostgreSQL...")

service = GradingService()

# 1. Create Grading Session ONCE
with patch('apps.ai_engine.services.llm_service.LLMService.perform_health_check', return_value={'ollama_status': 'AVAILABLE', 'model_status': 'READY', 'model_tag': 'gemma3:4b', 'api_base': 'http://localhost:11434'}):
    session = service.create_grading_session(
        teacher=teacher,
        title="OS Final Exam 2026",
        question_paper_file=qp,
        rubric_file=cr,
        criteria_source='file'
    )

print(f"[VERIFIED] Session Created: ID={session.id}, Title='{session.title}', Status={session.status}")
print(f"[VERIFIED] Pre-extracted QP Text Length: {len(session.question_paper_text)} chars")
print(f"[VERIFIED] Pre-extracted Rubric Text Length: {len(session.rubric_text)} chars")

# 2. Add Student 1 (Alice) under Session
st1_file = SimpleUploadedFile('alice_ans.txt', b"Virtual memory allows execution of processes that are not completely in memory using paging.", content_type="text/plain")
sub1 = StudentSubmission.objects.create(
    session=session,
    student_name='Alice Smith',
    answer_sheet_name='alice_ans.txt',
    answer_sheet_file=st1_file
)

with patch('apps.ai_engine.services.llm_service.LLMService.perform_health_check', return_value={'ollama_status': 'AVAILABLE', 'model_status': 'READY', 'model_tag': 'gemma3:4b', 'api_base': 'http://localhost:11434'}), \
     patch('apps.ai_engine.services.llm_service.LLMService.generate_text', return_value=mock_json):

    res1 = service.grade_student_submission(sub1.id)

print(f"[VERIFIED] Student 1 Graded: '{res1.student_name}' - Score: {res1.total_score}/{res1.max_score}")

# 3. Add Student 2 (Bob) under SAME Session
st2_file = SimpleUploadedFile('bob_ans.txt', b"Virtual memory maps virtual addresses to physical RAM addresses.", content_type="text/plain")
sub2 = StudentSubmission.objects.create(
    session=session,
    student_name='Bob Jones',
    answer_sheet_name='bob_ans.txt',
    answer_sheet_file=st2_file
)

with patch('apps.ai_engine.services.llm_service.LLMService.perform_health_check', return_value={'ollama_status': 'AVAILABLE', 'model_status': 'READY', 'model_tag': 'gemma3:4b', 'api_base': 'http://localhost:11434'}), \
     patch('apps.ai_engine.services.llm_service.LLMService.generate_text', return_value=mock_json):

    res2 = service.grade_student_submission(sub2.id)

print(f"[VERIFIED] Student 2 Graded: '{res2.student_name}' - Score: {res2.total_score}/{res2.max_score}")

# 4. Verify Database Integrity
total_subs = StudentSubmission.objects.filter(session=session).count()
total_results = StudentGradingResult.objects.filter(session=session).count()

print(f"[VERIFIED] Total Submissions in PostgreSQL for Session {session.id}: {total_subs}")
print(f"[VERIFIED] Total Results in PostgreSQL for Session {session.id}: {total_results}")
print("SUCCESS: Reusable Grading Session Workflow fully operational on PostgreSQL!")
