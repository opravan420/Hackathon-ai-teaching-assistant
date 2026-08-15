from django.urls import path
from . import views

urlpatterns = [
    path('test/', views.ai_test_view, name='ai_test_view'),
]
