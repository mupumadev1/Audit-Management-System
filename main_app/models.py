from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    # Add custom fields if needed
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_set',  # Avoid conflicts with default User model
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_set',  # Avoid conflicts with default User model
        blank=True
    )


class Project(models.Model):
    project_id = models.AutoField(primary_key=True)
    project_name = models.CharField(max_length=255)
    description = models.TextField()
    supported_transactions_number = models.IntegerField()  #To store number of supported transactions
    supported_transactions_value = models.DecimalField(max_digits=15,
                                                       decimal_places=2)  #To store monetary values accurately
    unsupported_transactions_number = models.IntegerField()  #To store number of unsupported transactions
    unsupported_transactions_value = models.DecimalField(max_digits=15,
                                                         decimal_places=2)  #To store monetary values accurately
    last_synced = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('error', 'Error')
    ], default='pending')

    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.project_name

    def get_total_transactions(self):
        return self.supported_transactions_number + self.unsupported_transactions_number

    def get_total_value(self):
        return self.supported_transactions_value + self.unsupported_transactions_value


class SyncLog(models.Model):
    class Meta:
        db_table = 'sync_logs'

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    sync_started = models.DateTimeField(auto_now_add=True)
    sync_completed = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ])
    records_processed = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.project.project_name} - {self.sync_started}"


class DatabaseMapping(models.Model):
    class Meta:
        db_table = 'database_mappings'

    project_name = models.CharField(max_length=255)
    sql_server_db = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.project_name} -> {self.sql_server_db}"
