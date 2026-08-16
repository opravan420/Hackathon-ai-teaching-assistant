from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import GradingSession, StudentGradingResult, QuestionScore
from .services import GradingService, GradingError
from apps.ai_engine.exceptions import LLMError

@login_required
def grading_dashboard(request):
    sessions = GradingSession.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'grading/dashboard.html', {'sessions': sessions})

@login_required
def grading_create(request):
    if request.method == 'POST':
        question_paper = request.FILES.get('question_paper')
        master_answer = request.FILES.get('master_answer')
        rubric = request.FILES.get('rubric')
        student_name = request.POST.get('student_name', 'Student Name')
        student_image = request.FILES.get('student_image') # Student answer sheet file
        
        try:
            default_max_marks = float(request.POST.get('default_max_marks', 5.0))
        except (ValueError, TypeError):
            default_max_marks = 5.0

        if not question_paper or not master_answer or not student_image:
            messages.error(request, "Please upload Question Paper, Answer Key, and Student Answer Sheet.")
            return redirect('grading_create')

        grading_service = GradingService()
        try:
            result = grading_service.grade_student_sheet(
                teacher=request.user,
                question_paper_file=question_paper,
                master_answer_file=master_answer,
                student_answer_file=student_image,
                rubric_file=rubric,
                student_name=student_name,
                default_max_marks=default_max_marks
            )
            messages.success(request, f"Student sheet for '{result.student_name}' graded successfully!")
            return redirect('grading_result_review', result_id=result.id)

        except (ValueError, GradingError, LLMError) as err:
            messages.error(request, f"An error occurred while grading the answers: {str(err)}")
            return redirect('grading_create')
        except Exception as e:
            messages.error(request, f"An error occurred while grading the answers: {str(e)}")
            return redirect('grading_create')

    return render(request, 'grading/create.html')

@login_required
def grading_session_detail(request, session_id):
    session = get_object_or_404(GradingSession, id=session_id, teacher=request.user)
    results = session.results.all()
    return render(request, 'grading/session_detail.html', {'session': session, 'results': results})

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
                    # Enforce non-negative score <= max_score
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
        result.save()
        messages.success(request, "Evaluation review changes saved successfully.")
        return redirect('grading_result_review', result_id=result.id)
        
    return render(request, 'grading/review.html', {'result': result})
