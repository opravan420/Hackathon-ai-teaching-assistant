from django.urls import path
from . import views

urlpatterns = [
    path('', views.grading_dashboard, name='grading_dashboard'),
    path('create/', views.grading_create, name='grading_create'),
    path('session/<int:session_id>/', views.grading_session_detail, name='grading_session_detail'),
    path('session/<int:session_id>/grade/', views.grade_student_ajax, name='grade_student_ajax'),
    path('submission/<int:submission_id>/retry/', views.retry_student_ajax, name='retry_student_ajax'),
    path('review/<int:result_id>/', views.grading_result_review, name='grading_result_review'),
]
