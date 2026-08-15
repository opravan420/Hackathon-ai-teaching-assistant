from django.urls import path
from . import views

urlpatterns = [
    path('', views.summary_dashboard, name='summary_dashboard'),
    path('create/', views.summary_create, name='summary_create'),
    path('review/<int:summary_id>/', views.summary_review, name='summary_review'),
    path('download/pdf/<int:summary_id>/', views.summary_download_pdf, name='summary_download_pdf'),
    path('download/docx/<int:summary_id>/', views.summary_download_docx, name='summary_download_docx'),
]
