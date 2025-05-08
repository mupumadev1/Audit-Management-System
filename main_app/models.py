from django.db import models

class Project(models.Model):
    project_name = models.CharField(max_length=255)
    description = models.TextField()
    supported_transactions_number = models.IntegerField() #To store number of supported transactions
    supported_transactions_value = models.DecimalField(max_digits=15, decimal_places=2) #To store monetary values accurately
    unsupported_transactions_number = models.IntegerField() #To store number of unsupported transactions
    unsupported_transactions_value = models.DecimalField(max_digits=15, decimal_places=2) #To store monetary values accurately

    def __str__(self):
        return self.project_name

