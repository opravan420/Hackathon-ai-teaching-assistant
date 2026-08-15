from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Quiz, Question, QuestionOption

@login_required
def quiz_dashboard(request):
    quizzes = Quiz.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'quiz/dashboard.html', {'quizzes': quizzes})

@login_required
def quiz_create(request):
    if request.method == 'POST':
        topic = request.POST.get('topic')
        difficulty = request.POST.get('difficulty', Quiz.MEDIUM)
        num_questions = int(request.POST.get('num_questions', 5))
        source_file = request.FILES.get('source_file')
        
        # Save Quiz shell
        source_file_name = source_file.name if source_file else "None"
        quiz = Quiz.objects.create(
            teacher=request.user,
            topic=topic,
            difficulty=difficulty,
            num_questions=num_questions,
            source_file_name=source_file_name
        )
        
        # Phase 1: Mock generated questions
        for i in range(1, num_questions + 1):
            q = Question.objects.create(
                quiz=quiz,
                text=f"Mock Question {i}: What is the core definition of the topic '{topic}'?",
                explanation=f"This is a mock explanation for question {i} under {difficulty} difficulty."
            )
            QuestionOption.objects.create(question=q, text="Mock Option A (Correct)", is_correct=True)
            QuestionOption.objects.create(question=q, text="Mock Option B", is_correct=False)
            QuestionOption.objects.create(question=q, text="Mock Option C", is_correct=False)
            QuestionOption.objects.create(question=q, text="Mock Option D", is_correct=False)
            
        messages.success(request, "AI Quiz generated successfully (Simulation)!")
        return redirect('quiz_review', quiz_id=quiz.id)
        
    return render(request, 'quiz/create.html', {
        'difficulties': Quiz.DIFFICULTY_CHOICES
    })

@login_required
def quiz_review(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)
    if request.method == 'POST':
        # Handle editing of questions and options
        for question in quiz.questions.all():
            q_text = request.POST.get(f"question_{question.id}")
            if q_text:
                question.text = q_text
                question.save()
            for option in question.options.all():
                opt_text = request.POST.get(f"option_{option.id}")
                if opt_text:
                    option.text = opt_text
                    option.save()
        messages.success(request, "Quiz changes saved successfully.")
        return redirect('quiz_review', quiz_id=quiz.id)
        
    return render(request, 'quiz/review.html', {'quiz': quiz})

@login_required
def quiz_accept(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)
    quiz.is_accepted = True
    quiz.save()
    messages.success(request, f"Quiz on '{quiz.topic}' has been accepted and finalized!")
    return redirect('quiz_dashboard')
