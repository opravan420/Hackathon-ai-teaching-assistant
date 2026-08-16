from django.urls import path
from . import views

urlpatterns = [
    path('test/', views.ai_test_view, name='ai_test_view'),
    path('documents/test/', views.ai_document_test_view, name='ai_document_test_view'),
]
