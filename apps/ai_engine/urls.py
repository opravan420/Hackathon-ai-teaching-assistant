from django.urls import path
from . import views

urlpatterns = [
    path('test/', views.ai_test_view, name='ai_test_view'),
    path('documents/test/', views.ai_document_test_view, name='ai_document_test_view'),
    path('rag/test/', views.ai_rag_test_view, name='ai_rag_test_view'),
    path('rag-gemma/test/', views.ai_rag_gemma_test_view, name='ai_rag_gemma_test_view'),
    path('task-status/<str:task_id>/', views.task_status_api, name='task_status_api'),
]
