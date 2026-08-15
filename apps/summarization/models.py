from django.db import models
from django.conf import settings

class LectureSummary(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='summaries')
    source_file_name = models.CharField(max_length=255)
    summary_text = models.TextField()
    is_satisfactory = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Summary of {self.source_file_name} by {self.teacher.username}"
