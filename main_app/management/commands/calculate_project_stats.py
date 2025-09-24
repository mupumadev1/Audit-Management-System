# management/commands/calculate_project_stats.py

from django.core.management.base import BaseCommand
from django.db.models import Sum, Count

from main_app.models import Project, ProjectPeriodStats


class Command(BaseCommand):
    help = 'Calculate and cache project statistics by fiscal period'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fiscal-year',
            type=str,
            help='Specific fiscal year to calculate (optional)'
        )
        parser.add_argument(
            '--project-id',
            type=int,
            help='Specific project ID to calculate (optional)'
        )

    def handle(self, *args, **options):
        fiscal_year = options.get('fiscal_year')
        project_id = options.get('project_id')

        projects = Project.objects.all()
        if project_id:
            projects = projects.filter(project_id=project_id)

        self.stdout.write(f"Processing {projects.count()} projects...")

        for project in projects:
            self.calculate_project_stats(project, fiscal_year)

        self.stdout.write(
            self.style.SUCCESS('Successfully calculated project statistics')
        )

    def calculate_project_stats(self, project, fiscal_year=None):
        """Calculate stats for a specific project"""
        documents = project.supportingdocument_set.all()

        if fiscal_year:
            years = [fiscal_year]
        else:
            years = documents.values_list('fiscal_year', flat=True).distinct()

        for year in years:
            year_docs = documents.filter(fiscal_year=year)
            periods = year_docs.values_list('fiscal_period', flat=True).distinct()

            for period in periods:
                period_docs = year_docs.filter(fiscal_period=period)

                supported_docs = period_docs.filter(supported=True)
                unsupported_docs = period_docs.filter(supported=False)

                supported_count = supported_docs.count()
                unsupported_count = unsupported_docs.count()
                supported_value = supported_docs.aggregate(
                    total=Sum('transaction_value'))['total'] or 0
                unsupported_value = unsupported_docs.aggregate(
                    total=Sum('transaction_value'))['total'] or 0

                # Update or create the cached stats
                ProjectPeriodStats.objects.update_or_create(
                    project=project,
                    fiscal_year=year,
                    fiscal_period=period,
                    defaults={
                        'supported_transactions_number': supported_count,
                        'supported_transactions_value': supported_value,
                        'unsupported_transactions_number': unsupported_count,
                        'unsupported_transactions_value': unsupported_value,
                    }
                )

                self.stdout.write(f"Updated stats for {project.project_name} - {year}/{period}")