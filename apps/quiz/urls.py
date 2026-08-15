from django.urls import path
from . import views

urlpatterns = [
    path('', views.quiz_dashboard, name='quiz_dashboard'),
    path('create/', views.quiz_create, name='quiz_create'),
    path('review/<int:quiz_id>/', views.quiz_review, name='quiz_review'),
    path('accept/<int:quiz_id>/', views.quiz_accept, name='quiz_accept'),
]
