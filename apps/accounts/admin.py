from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.accounts.models import User, TeacherProfile

class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Roles & Metadata', {'fields': ('role',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Roles & Metadata', {'fields': ('role',)}),
    )

class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'user', 'department', 'created_at')
    search_fields = ('employee_id', 'user__username', 'user__email', 'department')
    list_filter = ('department',)

admin.site.register(User, UserAdmin)
admin.site.register(TeacherProfile, TeacherProfileAdmin)

