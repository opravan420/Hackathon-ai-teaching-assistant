from django.urls import path
from . import views

urlpatterns = [
    path('', views.grading_dashboard, name='grading_dashboard'),
    path('create/', views.grading_create, name='grading_create'),
    path('session/<int:session_id>/', views.grading_session_detail, name='grading_session_detail'),
    path('review/<int:result_id>/', views.grading_result_review, name='grading_result_review'),
]
