from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.urls import reverse

def get_role_dashboard_url(user):
    if user.is_superuser or user.role == 'ADMIN':
        return '/admin/'
    elif user.role == 'TEACHER':
        return reverse('teacher_dashboard')
    return '/'

def login_view(request):
    if request.user.is_authenticated:
        return redirect(get_role_dashboard_url(request.user))
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(get_role_dashboard_url(user))
    else:
        form = AuthenticationForm(request)
        
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    if request.method == 'POST' or request.method == 'GET':
        logout(request)
        return redirect('login')

@login_required
def profile_view(request):
    profile = None
    if request.user.role == 'TEACHER':
        profile = getattr(request.user, 'teacher_profile', None)
        
    return render(request, 'accounts/profile.html', {
        'user': request.user,
        'profile': profile
    })

@login_required
def teacher_dashboard(request):
    if request.user.role != 'TEACHER' and not request.user.is_superuser:
        return redirect('login')
    
    from apps.quiz.models import Quiz
    from apps.summarization.models import LectureSummary
    from apps.grading.models import GradingSession
    
    quiz_count = Quiz.objects.filter(teacher=request.user).count()
    summary_count = LectureSummary.objects.filter(teacher=request.user).count()
    grading_count = GradingSession.objects.filter(teacher=request.user).count()
    
    return render(request, 'accounts/dashboard.html', {
        'quiz_count': quiz_count,
        'summary_count': summary_count,
        'grading_count': grading_count,
    })


