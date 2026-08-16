from django.db import models
from django.conf import settings

class Document(models.Model):
    PENDING = 'PENDING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    NO_EXTRACTABLE_TEXT = 'NO_EXTRACTABLE_TEXT'

    EXTRACTION_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (SUCCESS, 'Success'),
        (FAILED, 'Failed'),
        (NO_EXTRACTABLE_TEXT, 'No Extractable Text'),
    ]

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    original_filename = models.CharField(max_length=255)
    stored_file = models.FileField(upload_to='documents/')
    file_type = models.CharField(max_length=10)  # e.g., PDF, DOCX, PPTX, TXT
    file_size = models.PositiveIntegerField()  # Size in bytes
    UNINDEXED = 'UNINDEXED'
    PROCESSING = 'PROCESSING'
    INDEXED = 'INDEXED'
    INDEX_FAILED = 'FAILED'

    INDEXING_STATUS_CHOICES = [
        (UNINDEXED, 'Unindexed'),
        (PROCESSING, 'Processing'),
        (INDEXED, 'Indexed'),
        (INDEX_FAILED, 'Failed'),
    ]

    extraction_status = models.CharField(
        max_length=20,
        choices=EXTRACTION_STATUS_CHOICES,
        default=PENDING
    )
    indexing_status = models.CharField(
        max_length=20,
        choices=INDEXING_STATUS_CHOICES,
        default=UNINDEXED
    )
    extracted_text = models.TextField(blank=True, default='')
    character_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.original_filename} ({self.file_type}) - {self.extraction_status}"
