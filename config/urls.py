"""
URL configuration for AI Faculty Teaching Assistant project.
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def root_redirect(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.role == 'ADMIN':
            return redirect('admin:index')
        elif request.user.role == 'TEACHER':
            return redirect('teacher_dashboard')
    return redirect('login')

from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', root_redirect, name='root_redirect'),
    path('accounts/', include('apps.accounts.urls')),
    path('quiz/', include('apps.quiz.urls')),
    path('summarization/', include('apps.summarization.urls')),
    path('grading/', include('apps.grading.urls')),
    path('ai/', include('apps.ai_engine.urls')),
]

