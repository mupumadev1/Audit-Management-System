from django.contrib import admin
from .models import Project, SyncLog, DatabaseMapping
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin


# Register your models here.


class ProjectAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site):
        # Dynamically set list_display to all field names
        self.list_display = [field.name for field in model._meta.fields]
        super().__init__(model, admin_site)

class SyncLogAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site):
        # Dynamically set list_display to all field names
        self.list_display = [field.name for field in model._meta.fields]
        super().__init__(model, admin_site)


class DatabaseMappingAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site):
        # Dynamically set list_display to all field names
        self.list_display = [field.name for field in model._meta.fields]
        super().__init__(model, admin_site)


admin.site.register(Project, ProjectAdmin)
admin.site.register(SyncLog, SyncLogAdmin)
admin.site.register(DatabaseMapping, DatabaseMappingAdmin)

# Register the custom user model with the admin site
CustomUser = get_user_model()
admin.site.register(CustomUser, UserAdmin)
