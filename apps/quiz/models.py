from django.db import models
from django.conf import settings

class Quiz(models.Model):
    EASY = 'EASY'
    MEDIUM = 'MEDIUM'
    HARD = 'HARD'
    DIFFICULTY_CHOICES = [
        (EASY, 'Easy'),
        (MEDIUM, 'Medium'),
        (HARD, 'Hard'),
    ]

    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quizzes')
    topic = models.CharField(max_length=255)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default=MEDIUM)
    num_questions = models.IntegerField(default=5)
    source_file_name = models.CharField(max_length=255, blank=True, null=True)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.topic} ({self.difficulty}) - {self.num_questions} Qs"

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    explanation = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Q: {self.text[:50]}..."

class QuestionOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Incorrect'})"
