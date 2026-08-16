from django.db import models
from django.conf import settings

class GradingSession(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('PROCESSING', 'Processing Context'),
        ('READY', 'Ready for Grading'),
        ('FAILED', 'Context Processing Failed'),
    )

    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='grading_sessions')
    title = models.CharField(max_length=255, default='Untitled Grading Session')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='READY')
    
    question_paper_name = models.CharField(max_length=255)
    question_paper_text = models.TextField(blank=True, null=True)
    
    master_answer_name = models.CharField(max_length=255, default='None', blank=True, null=True)
    master_answer_text = models.TextField(blank=True, null=True)
    
    criteria_source = models.CharField(max_length=10, choices=[('file', 'File'), ('manual', 'Manual')], default='file')
    rubric_name = models.CharField(max_length=255, default='None', blank=True, null=True)
    rubric_text = models.TextField(blank=True, null=True)
    
    evaluation_criteria = models.TextField(blank=True, null=True)
    additional_instructions = models.TextField(blank=True, null=True)
    default_max_marks = models.FloatField(default=5.0)
    
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} (Session {self.id}) - by {self.teacher.username}"


class StudentSubmission(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing AI Evaluation'),
        ('COMPLETED', 'Grading Completed'),
        ('FAILED', 'Evaluation Failed'),
    )

    session = models.ForeignKey(GradingSession, on_delete=models.CASCADE, related_name='submissions')
    student_name = models.CharField(max_length=100)
    answer_sheet_name = models.CharField(max_length=255)
    answer_sheet_file = models.FileField(upload_to='student_answers/', blank=True, null=True)
    extracted_text = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    task_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    progress = models.IntegerField(default=0)
    current_stage = models.CharField(max_length=50, default='CREATED')
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Submission {self.id}: {self.student_name} - {self.status}"


class StudentGradingResult(models.Model):
    submission = models.OneToOneField(StudentSubmission, on_delete=models.CASCADE, related_name='result', null=True, blank=True)
    session = models.ForeignKey(GradingSession, on_delete=models.CASCADE, related_name='results')
    student_name = models.CharField(max_length=100)
    answer_sheet_name = models.CharField(max_length=255)
    total_score = models.FloatField(default=0.0)
    max_score = models.FloatField(default=0.0)
    overall_feedback = models.TextField(blank=True, null=True)
    is_manually_overridden = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
