import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ADMIN = 'ADMIN'
    TEACHER = 'TEACHER'
    
    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (TEACHER, 'Teacher'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=TEACHER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.role})"


class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.employee_id})"

