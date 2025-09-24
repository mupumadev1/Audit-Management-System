from django.apps import AppConfig


class MainAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main_app'

    """def ready(self):
        # Import and start scheduler when Django starts
        from . import sync_tasks
        sync_tasks.start_scheduler()"""