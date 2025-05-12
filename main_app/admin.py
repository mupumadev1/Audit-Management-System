from django.contrib import admin
from .models import Project
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
# Register your models here.


class ProjectAdmin(admin.ModelAdmin):
    list_display = ('project_name', 'supported_transactions_number', 'supported_transactions_value', 'unsupported_transactions_number', 'unsupported_transactions_value')
    list_filter = ('supported_transactions_value', 'unsupported_transactions_value')

admin.site.register(Project, ProjectAdmin)

# Register the custom user model with the admin site
CustomUser = get_user_model()
admin.site.register(CustomUser, UserAdmin)