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
    project_name = models.CharField(max_length=255)
    description = models.TextField()
    supported_transactions_number = models.IntegerField() #To store number of supported transactions
    supported_transactions_value = models.DecimalField(max_digits=15, decimal_places=2) #To store monetary values accurately
    unsupported_transactions_number = models.IntegerField() #To store number of unsupported transactions
    unsupported_transactions_value = models.DecimalField(max_digits=15, decimal_places=2) #To store monetary values accurately

    def __str__(self):
        return self.project_name

