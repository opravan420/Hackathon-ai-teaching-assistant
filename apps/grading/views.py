import threading
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.db import connection

from .models import GradingSession, StudentSubmission, StudentGradingResult, QuestionScore
from .services import GradingService, GradingError
from apps.ai_engine.exceptions import LLMError
from apps.ai_engine.services.llm_service import LLMService
from apps.ai_engine.task_tracker import TaskTracker

logger = logging.getLogger(__name__)

@login_required
def grading_dashboard(request):
    sessions = GradingSession.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'grading/dashboard.html', {'sessions': sessions})

@login_required
def grading_create(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        question_paper = request.FILES.get('question_paper')
        master_answer = request.FILES.get('master_answer')
        rubric = request.FILES.get('rubric')
        criteria_source = request.POST.get('criteria_source', 'file')
        evaluation_criteria = request.POST.get('evaluation_criteria', '').strip()
        additional_instructions = request.POST.get('additional_instructions', '').strip()
        
        try:
            default_max_marks = float(request.POST.get('default_max_marks', 5.0))
        except (ValueError, TypeError):
            default_max_marks = 5.0

        if not question_paper:
            messages.error(request, "Please upload a Question Paper document.")
            return redirect('grading_create')

        # Check LLM Availability
        llm_service = LLMService()
        health = llm_service.perform_health_check()
        if health["ollama_status"] != "AVAILABLE":
            msg = f"AI Engine Error: Local Ollama service is unavailable ({health.get('reason')}). Please start Ollama server."
            messages.error(request, msg)
            return redirect('grading_create')

        grading_service = GradingService()

        try:
            session = grading_service.create_grading_session(
                teacher=request.user,
                title=title,
                question_paper_file=question_paper,
                master_answer_file=master_answer,
                rubric_file=rubric,
                criteria_source=criteria_source,
                evaluation_criteria=evaluation_criteria,
                additional_instructions=additional_instructions,
                default_max_marks=default_max_marks
            )
            messages.success(request, f"Grading session '{session.title}' created successfully! You can now grade student answer sheets under this session.")
            return redirect('grading_session_detail', session_id=session.id)

        except (ValueError, GradingError) as err:
            messages.error(request, str(err))
            return redirect('grading_create')
        except Exception as e:
            logger.error(f"Error creating grading session: {e}", exc_info=True)
            messages.error(request, f"An unexpected error occurred: {str(e)}")
            return redirect('grading_create')

    llm_health = LLMService().perform_health_check()
    return render(request, 'grading/create.html', {'llm_health': llm_health})

@login_required
def grading_session_detail(request, session_id):
    session = get_object_or_404(GradingSession, id=session_id, teacher=request.user)
    submissions = session.submissions.all().order_by('-created_at')
    llm_health = LLMService().perform_health_check()
    return render(request, 'grading/session_detail.html', {
        'session': session,
        'submissions': submissions,
        'llm_health': llm_health
    })

@login_required
def grade_student_ajax(request, session_id):
    session = get_object_or_404(GradingSession, id=session_id, teacher=request.user)
    
    if request.method != 'POST':
        return JsonResponse({'status': 'FAILED', 'error': 'Invalid request method.'}, status=405)

    student_name = request.POST.get('student_name', '').strip()
    student_image = request.FILES.get('student_image')

    if not student_name or not student_image:
        return JsonResponse({'status': 'FAILED', 'error': 'Student Name and Answer Sheet are required.'}, status=400)

    # Check LLM Health
    health = LLMService().perform_health_check()
    if health["ollama_status"] != "AVAILABLE":
        return JsonResponse({'status': 'FAILED', 'error': f"Ollama unavailable: {health.get('reason')}"}, status=400)

    # Create persistent StudentSubmission
    submission = StudentSubmission.objects.create(
        session=session,
        student_name=student_name,
        answer_sheet_name=getattr(student_image, 'name', 'student_answer'),
        answer_sheet_file=student_image,
        status='PENDING'
    )

    tracker = TaskTracker()
    task_id = tracker.create_task('grading', f"Evaluating '{student_name}' Answer Sheet via AI")
    submission_id = submission.id

    def async_worker():
        connection.close()
        try:
            service = GradingService()
            result = service.grade_student_submission(submission_id=submission_id, task_id=task_id)
            redirect_url = reverse('grading_result_review', kwargs={'result_id': result.id})
            tracker.complete_task(task_id, f"Graded '{student_name}' successfully!", redirect_url=redirect_url)
        except Exception as e:
            logger.error(f"Worker failed for submission {submission_id}: {e}", exc_info=True)
            tracker.fail_task(task_id, str(e))
        finally:
            connection.close()

    t = threading.Thread(target=async_worker)
    t.start()

    return JsonResponse({'status': 'STARTED', 'task_id': task_id, 'submission_id': submission_id})

@login_required
def retry_student_ajax(request, submission_id):
    submission = get_object_or_404(StudentSubmission, id=submission_id, session__teacher=request.user)
    
    if request.method != 'POST':
        return JsonResponse({'status': 'FAILED', 'error': 'Invalid request method.'}, status=405)

    tracker = TaskTracker()
    task_id = tracker.create_task('grading', f"Retrying evaluation for '{submission.student_name}'")
    sub_id = submission.id

    def async_worker():
        connection.close()
        try:
            service = GradingService()
            result = service.grade_student_submission(submission_id=sub_id, task_id=task_id)
            redirect_url = reverse('grading_result_review', kwargs={'result_id': result.id})
            tracker.complete_task(task_id, f"Regraded '{submission.student_name}' successfully!", redirect_url=redirect_url)
        except Exception as e:
            logger.error(f"Retry worker failed for submission {sub_id}: {e}", exc_info=True)
            tracker.fail_task(task_id, str(e))
        finally:
            connection.close()

    t = threading.Thread(target=async_worker)
    t.start()

    return JsonResponse({'status': 'STARTED', 'task_id': task_id, 'submission_id': sub_id})

@login_required
def grading_result_review(request, result_id):
    result = get_object_or_404(StudentGradingResult, id=result_id, session__teacher=request.user)
    if request.method == 'POST':
        total = 0.0
        for score in result.question_scores.all():
            val = request.POST.get(f"score_{score.id}")
            comment = request.POST.get(f"comment_{score.id}")
            if val is not None:
                try:
                    score_val = float(val)
                    if score_val < 0.0:
                        score_val = 0.0
                    if score_val > score.max_score:
                        score_val = score.max_score
                    score.score_given = score_val
                except (ValueError, TypeError):
                    pass
                if comment is not None:
                    score.feedback = comment.strip()
                score.save()
            total += score.score_given

        result.total_score = round(total, 2)
        overall_fb = request.POST.get('overall_feedback')
        if overall_fb is not None:
            result.overall_feedback = overall_fb.strip()
        result.is_manually_overridden = True
        result.save()
        messages.success(request, "Evaluation review changes saved successfully.")
        return redirect('grading_result_review', result_id=result.id)
        
    return render(request, 'grading/review.html', {'result': result})
