import os
import sys
from django.core.files.uploadedfile import SimpleUploadedFile

sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding='utf-8')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DATABASE_URL'] = ''
import django
django.setup()

from django.core.management import call_command
call_command('migrate', verbosity=0)

from django.contrib.auth import get_user_model
from apps.quiz.services import QuizService
from apps.summarization.services import SummarizationService
from apps.grading.services import GradingService

User = get_user_model()
teacher, _ = User.objects.get_or_create(username='verify_llm_t1', defaults={'role': User.TEACHER})

sample_deadlock_bytes = (
    b"Deadlock in Operating Systems occurs when a set of processes are blocked because each process "
    b"holds a resource and waits for another resource held by some other process.\n\n"
    b"The four necessary conditions for deadlock are:\n"
    b"1. Mutual Exclusion: At least one resource must be held in a non-shareable mode.\n"
    b"2. Hold and Wait: A process must be holding at least one resource and waiting to acquire additional resources.\n"
    b"3. No Preemption: Resources cannot be preempted; a resource can be released only voluntarily.\n"
    b"4. Circular Wait: A set of waiting processes must exist such that P0 waits for P1, P1 waits for P2, and Pn waits for P0.\n"
)

print("\n==================================================")
print("TEST 1 — QUIZ TOPIC ONLY")
print("==================================================")
quiz_service = QuizService()
quiz1 = quiz_service.generate_quiz(
    teacher=teacher,
    topic="Deadlock",
    difficulty="EASY",
    num_questions=5,
    uploaded_file=None
)
print(f"Status: SUCCESS | Quiz ID: {quiz1.id} | Topic: '{quiz1.topic}' | Questions: {quiz1.questions.count()}")
for q in quiz1.questions.all()[:2]:
    print(f" - Q: {q.text[:80]} | Correct: {q.options.filter(is_correct=True).first().text}")

print("\n==================================================")
print("TEST 2 — QUIZ FILE ONLY")
print("==================================================")
file_only_upload = SimpleUploadedFile("deadlock_file_only.txt", sample_deadlock_bytes, content_type="text/plain")
quiz2 = quiz_service.generate_quiz(
    teacher=teacher,
    topic="",
    difficulty="EASY",
    num_questions=5,
    uploaded_file=file_only_upload
)
print(f"Status: SUCCESS | Quiz ID: {quiz2.id} | Source: {quiz2.source_file_name} | Questions: {quiz2.questions.count()}")
for q in quiz2.questions.all()[:2]:
    print(f" - Q: {q.text[:80]} | Correct: {q.options.filter(is_correct=True).first().text}")

print("\n==================================================")
print("TEST 3 — QUIZ FILE + TOPIC")
print("==================================================")
file_topic_upload = SimpleUploadedFile("deadlock_file_topic.txt", sample_deadlock_bytes, content_type="text/plain")
quiz3 = quiz_service.generate_quiz(
    teacher=teacher,
    topic="Deadlock",
    difficulty="MEDIUM",
    num_questions=5,
    uploaded_file=file_topic_upload
)
print(f"Status: SUCCESS | Quiz ID: {quiz3.id} | Topic: '{quiz3.topic}' | Questions: {quiz3.questions.count()}")

print("\n==================================================")
print("TEST 4 — SUMMARIZATION")
print("==================================================")
sum_upload = SimpleUploadedFile("deadlock_lecture.txt", sample_deadlock_bytes, content_type="text/plain")
sum_service = SummarizationService()
summary = sum_service.generate_summary(
    teacher=teacher,
    uploaded_file=sum_upload,
    custom_instruction="Summarize in bullet points."
)
print(f"Status: SUCCESS | Summary ID: {summary.id} | Length: {len(summary.summary_text)} chars")
print("Snippet:", summary.summary_text[:150], "...")

print("\n==================================================")
print("TEST 5 — GRADING")
print("==================================================")
qp = SimpleUploadedFile("qp.txt", b"Q1 (5 Marks): What are the four conditions for deadlock?", content_type="text/plain")
key = SimpleUploadedFile("key.txt", b"Q1: Mutual exclusion, hold and wait, no preemption, circular wait.", content_type="text/plain")
student_ans = SimpleUploadedFile("student.txt", b"Deadlock conditions are mutual exclusion, hold and wait, no preemption, and circular wait.", content_type="text/plain")

grading_service = GradingService()
result = grading_service.grade_student_sheet(
    teacher=teacher,
    question_paper_file=qp,
    master_answer_file=key,
    student_answer_file=student_ans,
    student_name="Alice"
)
print(f"Status: SUCCESS | Student: {result.student_name} | Score: {result.total_score}/{result.max_score}")
for sc in result.question_scores.all():
    print(f" - {sc.question_number}: {sc.score_given}/{sc.max_score} | Feedback: {sc.feedback[:80]}")

print("\nALL 5 INTEGRATION TESTS PASSED CLEANLY!")
