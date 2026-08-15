from django.db import models
from django.conf import settings

class GradingSession(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='grading_sessions')
    question_paper_name = models.CharField(max_length=255)
    master_answer_name = models.CharField(max_length=255)
    rubric_name = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session {self.id} - QP: {self.question_paper_name} by {self.teacher.username}"

class StudentGradingResult(models.Model):
    session = models.ForeignKey(GradingSession, on_delete=models.CASCADE, related_name='results')
    student_name = models.CharField(max_length=100)
    answer_sheet_name = models.CharField(max_length=255)
    total_score = models.FloatField(default=0.0)
    max_score = models.FloatField(default=0.0)
    overall_feedback = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student_name} - Graded {self.total_score}/{self.max_score}"

class QuestionScore(models.Model):
    grading_result = models.ForeignKey(StudentGradingResult, on_delete=models.CASCADE, related_name='question_scores')
    question_number = models.CharField(max_length=10) # e.g. "Q1"
    max_score = models.FloatField(default=5.0)
    score_given = models.FloatField(default=0.0)
    feedback = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.question_number}: {self.score_given}/{self.max_score}"
