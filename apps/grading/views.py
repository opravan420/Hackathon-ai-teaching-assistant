from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import GradingSession, StudentGradingResult, QuestionScore

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
        student_image = request.FILES.get('student_image')
        
        if not question_paper or not master_answer or not student_image:
            messages.error(request, "Please upload Question Paper, Answer Key, and Student Answer Sheet.")
            return redirect('grading_create')
            
        # Create session
        session = GradingSession.objects.create(
            teacher=request.user,
            question_paper_name=question_paper.name,
            master_answer_name=master_answer.name,
            rubric_name=rubric.name if rubric else "None"
        )
        
        # Create student result
        result = StudentGradingResult.objects.create(
            session=session,
            student_name=student_name,
            answer_sheet_name=student_image.name,
            total_score=12.0,
            max_score=15.0,
            overall_feedback="Excellent work overall. The student demonstrated good understanding, minor errors in Q2 calculation."
        )
        
        # Create question scores
        QuestionScore.objects.create(grading_result=result, question_number="Q1", max_score=5.0, score_given=5.0, feedback="Fully correct answer, matching master definition.")
        QuestionScore.objects.create(grading_result=result, question_number="Q2", max_score=5.0, score_given=3.0, feedback="Missing intermediate step in the derivation, but correct final result.")
        QuestionScore.objects.create(grading_result=result, question_number="Q3", max_score=5.0, score_given=4.0, feedback="Good explanation, could include more technical terms as per the rubric.")
        
        messages.success(request, "Student sheet graded successfully (Simulation)!")
        return redirect('grading_result_review', result_id=result.id)
        
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
        # Allow editing question scores
        total = 0.0
        for score in result.question_scores.all():
            val = request.POST.get(f"score_{score.id}")
            comment = request.POST.get(f"comment_{score.id}")
            if val is not None:
                score.score_given = float(val)
                score.feedback = comment
                score.save()
            total += score.score_given
        result.total_score = total
        result.overall_feedback = request.POST.get('overall_feedback')
        result.save()
        messages.success(request, "Evaluation review changes saved successfully.")
        return redirect('grading_result_review', result_id=result.id)
        
    return render(request, 'grading/review.html', {'result': result})
