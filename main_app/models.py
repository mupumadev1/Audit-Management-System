from decimal import Decimal

from django.db import models, connections
from django.contrib.auth.models import AbstractUser
from django.db.models import Sum
import logging
logger = logging.getLogger(__name__)

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


class SyncMetrics(models.Model):
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    execution_time = models.FloatField(null=True, blank=True)  # in seconds
    successful_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    total_projects = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ], default='running')

    class Meta:
        ordering = ['-started_at']


""" main_app/models.py"""


class Project(models.Model):
    project_id = models.AutoField(primary_key=True)
    project_name = models.CharField(max_length=255)
    description = models.TextField()
    last_synced = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('error', 'Error')
    ], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.project_name

    def get_total_transactions(self, fiscal_year=None, fiscal_period=None):
        """Get total number of transactions for this project"""
        stats = self.get_stats(fiscal_year=fiscal_year, fiscal_period=fiscal_period)
        return stats['total_count']

    def get_stats(self, fiscal_year=None, fiscal_period=None):
        """Get project statistics using the same logic as _get_aggregated_data"""
        # Try to get from ProjectPeriodStats first (if it exists and is recent)
        if fiscal_year and fiscal_period:
            try:
                cached_stats = ProjectPeriodStats.objects.get(
                    project=self,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period
                )
                # Use cached stats if they're recent (within last hour)
                from django.utils import timezone
                if (timezone.now() - cached_stats.last_calculated).seconds < 3600:
                    return {
                        'supported_count': cached_stats.supported_transactions_number,
                        'unsupported_count': cached_stats.unsupported_transactions_number,
                        'supported_value': cached_stats.supported_transactions_value,
                        'unsupported_value': cached_stats.unsupported_transactions_value,
                        'total_count': cached_stats.supported_transactions_number + cached_stats.unsupported_transactions_number,
                    }
            except ProjectPeriodStats.DoesNotExist:
                pass

        # Fall back to real-time calculation using the same logic as sync function
        return self._calculate_real_time_stats(fiscal_year, fiscal_period)

    def _calculate_real_time_stats(self, fiscal_year=None, fiscal_period=None):
        """Calculate stats in real-time using the same logic as _get_aggregated_data"""
        # Build filter for SupportingDocument queries
        supporting_docs_filter = {'project': self}
        if fiscal_year:
            supporting_docs_filter['fiscal_year'] = fiscal_year
        if fiscal_period:
            supporting_docs_filter['fiscal_period'] = fiscal_period

        # Get supported transactions from SupportingDocument table
        from transactions.models import SupportingDocument  # Adjust import as needed
        supported_docs = SupportingDocument.objects.filter(
            **supporting_docs_filter,
            supported=True
        )

        supported_count = supported_docs.count()
        supported_value = supported_docs.aggregate(
            total=Sum('transaction_value')
        )['total'] or Decimal('0')

        # Get unsupported transactions using the same logic as sync function
        unsupported_count, unsupported_value = self._get_unsupported_stats(
            fiscal_year, fiscal_period, supporting_docs_filter
        )

        return {
            'supported_count': supported_count,
            'unsupported_count': unsupported_count,
            'supported_value': supported_value,
            'unsupported_value': unsupported_value,
            'total_count': supported_count + unsupported_count,
        }

    def _get_unsupported_stats(self, fiscal_year, fiscal_period, supporting_docs_filter):
        """Get unsupported transaction stats from glpost table using composite keys - Raw SQL version"""
        try:
            # Get the database mapping for this project
            from .models import DatabaseMapping  # Adjust import as needed
            mapping = DatabaseMapping.objects.get(
                project_name=self.project_name,
                is_active=True
            )
            sql_server_db = mapping.sql_server_db
        except:
            # If no mapping found, return zeros
            return 0, Decimal('0')

        # Get list of supported batch/entry pairs for exclusion (composite keys)
        from transactions.models import SupportingDocument  # Adjust import as needed
        supported_batch_entry_pairs = list(
            SupportingDocument.objects.filter(
                **supporting_docs_filter,
                supported=True
            ).values_list('batchnbr', 'entrynbr').distinct()
        )

        # Build query conditions for glpost
        company_id = mapping.sql_server_db
        base_conditions = ["companyid = %s", "transamt > 0"]
        base_params = [company_id]

        if fiscal_year:
            base_conditions.append("FISCALYR = %s")
            base_params.append(fiscal_year)
        if fiscal_period:
            base_conditions.append("FISCALPERD = %s")
            base_params.append(fiscal_period)

        # Exclude supported batch-entry combinations using composite key
        if supported_batch_entry_pairs:
            # For large datasets, use LEFT JOIN with VALUES for better performance
            if len(supported_batch_entry_pairs) > 100:
                # Create VALUES clause for supported pairs
                values_list = []
                for batch_nbr, entry_nbr in supported_batch_entry_pairs:
                    values_list.append(f"({batch_nbr}, {entry_nbr})")

                supported_pairs_values = "VALUES " + ", ".join(values_list)

                where_clause = " AND ".join(base_conditions)

                # Modified queries using LEFT JOIN for exclusion
                unsupported_count_query = f"""
                    SELECT COUNT(*)
                    FROM (
                        SELECT DISTINCT g.BATCHNBR, g.ENTRYNBR
                        FROM [{company_id}].dbo.glpost g
                        LEFT JOIN ({supported_pairs_values}) AS supported(batch_val, entry_val)
                            ON g.BATCHNBR = supported.batch_val AND g.ENTRYNBR = supported.entry_val
                        WHERE {where_clause} AND supported.batch_val IS NULL AND SRCELEDGER='EN' AND SRCETYPE='EV'
                    ) AS distinct_combinations
                """

                unsupported_value_query = f"""
                    SELECT COALESCE(SUM(g.transamt), 0)
                    FROM [{company_id}].dbo.glpost g
                    LEFT JOIN ({supported_pairs_values}) AS supported(batch_val, entry_val)
                        ON g.BATCHNBR = supported.batch_val AND g.ENTRYNBR = supported.entry_val
                    WHERE {where_clause} AND supported.batch_val IS NULL AND SRCELEDGER='EN' AND SRCETYPE='EV'
                """
            else:
                # For smaller datasets, use NOT EXISTS or OR conditions
                composite_conditions = []
                for batch_nbr, entry_nbr in supported_batch_entry_pairs:
                    composite_conditions.append("(BATCHNBR = %s AND ENTRYNBR = %s)")
                    base_params.extend([batch_nbr, entry_nbr])

                # Combine all conditions with OR and wrap with NOT
                exclusion_clause = "NOT (" + " OR ".join(composite_conditions) + ")"
                base_conditions.append(exclusion_clause)

                where_clause = " AND ".join(base_conditions)

                unsupported_count_query = f"""
                    SELECT COUNT(*)
                    FROM (
                        SELECT DISTINCT BATCHNBR, ENTRYNBR
                        FROM [{company_id}].dbo.glpost
                        WHERE {where_clause} AND SRCELEDGER='EN' AND SRCETYPE='EV'
                    ) AS distinct_combinations
                """

                unsupported_value_query = f"""
                    SELECT COALESCE(SUM(transamt), 0)
                    FROM [{company_id}].dbo.glpost
                    WHERE {where_clause} AND SRCELEDGER='EN' AND SRCETYPE='EV'
                """
        else:
            # No supported pairs - all transactions are unsupported
            where_clause = " AND ".join(base_conditions)

            unsupported_count_query = f"""
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT BATCHNBR, ENTRYNBR
                    FROM [{company_id}].dbo.glpost
                    WHERE {where_clause} AND SRCELEDGER='EN' AND SRCETYPE='EV'
                ) AS distinct_combinations
            """

            unsupported_value_query = f"""
                SELECT COALESCE(SUM(transamt), 0)
                FROM [{company_id}].dbo.glpost
                WHERE {where_clause} AND SRCELEDGER='EN' AND SRCETYPE='EV'
            """

        try:
            connection = connections[sql_server_db]
            with connection.cursor() as cursor:
                # Execute count query
                cursor.execute(unsupported_count_query, base_params)
                unsupported_count = cursor.fetchone()[0] or 0

                # Execute value query
                cursor.execute(unsupported_value_query, base_params)
                unsupported_value = Decimal(str(cursor.fetchone()[0] or 0))

            return unsupported_count, unsupported_value

        except Exception as e:
            logger.error(f"Error calculating unsupported stats for project {self.project_name}: {str(e)}")
            return 0, Decimal('0')
    @property
    def supported_transactions_number(self):
        """Get number of supported transactions across all periods"""
        return self.supportingdocument_set.filter(supported=True).count()

    @property
    def unsupported_transactions_number(self):
        """Get number of unsupported transactions across all periods"""
        # This is complex to calculate across all periods without specific filters
        # Consider using the ProjectPeriodStats aggregation or real-time calculation
        stats = self.get_stats()
        return stats['unsupported_count']



class ProjectPeriodStats(models.Model):
    """Store pre-calculated stats for each project/period combination"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    fiscal_year = models.CharField(max_length=4)
    fiscal_period = models.CharField(max_length=2)
    supported_transactions_number = models.IntegerField(default=0)
    supported_transactions_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    unsupported_transactions_number = models.IntegerField(default=0)
    unsupported_transactions_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    last_calculated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['project', 'fiscal_year', 'fiscal_period']
        indexes = [
            models.Index(fields=['fiscal_year', 'fiscal_period']),
        ]


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
