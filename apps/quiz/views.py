from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Quiz, Question, QuestionOption
from .services import QuizService, QuizGenerationError
from apps.ai_engine.exceptions import LLMError

@login_required
def quiz_dashboard(request):
    quizzes = Quiz.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'quiz/dashboard.html', {'quizzes': quizzes})

@login_required
def quiz_create(request):
    if request.method == 'POST':
        topic = request.POST.get('topic', '').strip()
        difficulty = request.POST.get('difficulty', Quiz.MEDIUM)
        try:
            num_questions = int(request.POST.get('num_questions', 5))
        except (ValueError, TypeError):
            num_questions = 5

        source_file = request.FILES.get('source_file')
        
        quiz_service = QuizService()
        try:
            quiz = quiz_service.generate_quiz(
                teacher=request.user,
                topic=topic,
                difficulty=difficulty,
                num_questions=num_questions,
                uploaded_file=source_file
            )
            messages.success(request, "AI Quiz generated successfully!")
            return redirect('quiz_review', quiz_id=quiz.id)

        except ValueError as ve:
            messages.error(request, str(ve))
            return redirect('quiz_create')
        except (QuizGenerationError, LLMError) as err:
            messages.error(request, f"An error occurred while generating the quiz: {str(err)}")
            return redirect('quiz_create')
        except Exception as e:
            messages.error(request, f"An error occurred while generating the quiz: {str(e)}")
            return redirect('quiz_create')
        
    return render(request, 'quiz/create.html', {
        'difficulties': Quiz.DIFFICULTY_CHOICES
    })

@login_required
def quiz_review(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user)
    if request.method == 'POST':
        # Handle editing of questions, explanations, options, and correct selection
        for question in quiz.questions.all():
            q_text = request.POST.get(f"question_{question.id}")
            q_exp = request.POST.get(f"explanation_{question.id}")
            if q_text:
                question.text = q_text.strip()
            if q_exp is not None:
                question.explanation = q_exp.strip()
            question.save()

            correct_opt_id = request.POST.get(f"correct_option_{question.id}")
            for option in question.options.all():
                opt_text = request.POST.get(f"option_{option.id}")
                if opt_text:
                    option.text = opt_text.strip()
                if correct_opt_id:
                    option.is_correct = (str(option.id) == str(correct_opt_id))
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
