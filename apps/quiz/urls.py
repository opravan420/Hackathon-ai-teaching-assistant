from django.urls import path
from . import views

urlpatterns = [
    path('', views.quiz_dashboard, name='quiz_dashboard'),
    path('create/', views.quiz_create, name='quiz_create'),
    path('review/<int:quiz_id>/', views.quiz_review, name='quiz_review'),
    path('accept/<int:quiz_id>/', views.quiz_accept, name='quiz_accept'),
    path('download/<int:quiz_id>/qp/pdf/', views.download_question_paper_pdf, name='download_question_paper_pdf'),
    path('download/<int:quiz_id>/qp/docx/', views.download_question_paper_docx, name='download_question_paper_docx'),
    path('download/<int:quiz_id>/key/pdf/', views.download_answer_key_pdf, name='download_answer_key_pdf'),
    path('download/<int:quiz_id>/key/docx/', views.download_answer_key_docx, name='download_answer_key_docx'),
]
