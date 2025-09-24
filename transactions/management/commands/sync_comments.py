import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from main_app.models import DatabaseMapping, CustomUser
from ...models import Eneba, Enpjd, Glpost, Project, Comments


class Command(BaseCommand):
    help = 'Sync expense comments from SQL Server tables to Django models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fiscal-year',
            type=str,
            help='Sync specific fiscal year (e.g., 2024)',
        )
        parser.add_argument(
            '--fiscal-period',
            type=str,
            help='Sync specific fiscal period (e.g., 01)',
        )
        parser.add_argument(
            '--project-id',
            type=int,
            help='Sync for specific project ID',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes',
        )

    def handle(self, *args, **options):
        fiscal_year = options.get('fiscal_year')
        fiscal_period = options.get('fiscal_period')
        project_id = options.get('project_id')
        dry_run = options.get('dry_run')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        try:
            synced_count = self.sync_comments(  # Fixed: was sync_transactions
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                project_id=project_id,
                dry_run=dry_run
            )

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'Would sync {synced_count} transactions')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully synced {synced_count} transactions')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error syncing transactions: {str(e)}')
            )

    def sync_comments(self, project_id=None, fiscal_year=None, fiscal_period=None, dry_run=False):
        """
        Sync expense transactions from SQL Server tables to Django models
        """
        # Get active database mappings
        db_mappings = DatabaseMapping.objects.filter(is_active=True)
        project_names = [mapping.project_name for mapping in db_mappings]

        # Filter projects based on project_id if provided
        projects_query = Project.objects.filter(project_name__in=project_names)
        if project_id:
            projects_query = projects_query.filter(id=project_id)

        projects = projects_query.all()
        synced_count = 0

        for project in projects:
            self.stdout.write(f'Syncing project: {project.project_name}')

            try:
                sql_server_db = DatabaseMapping.objects.get(project_name=project.project_name)
            except DatabaseMapping.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'No database mapping found for project: {project.project_name}')
                )
                continue

            # Build GL post query
            glpost_query = Glpost.objects.using(sql_server_db.sql_server_db).filter(transamt__gt=0)

            if fiscal_year:
                glpost_query = glpost_query.filter(fiscalyr=fiscal_year)
            if fiscal_period:
                glpost_query = glpost_query.filter(fiscalperd=fiscal_period.zfill(2))

            project_glposts = glpost_query.all()

            for glpost in project_glposts:
                try:
                    # Find corresponding ENPJD records
                    enpjd_records = Enpjd.objects.using(sql_server_db.sql_server_db).filter(
                        iddoc=glpost.jnldtlref
                    )

                    if not enpjd_records.exists():
                        continue

                    # Find corresponding ENEBA records for attachments
                    for enpjd in enpjd_records:
                        eneba_records = Eneba.objects.using(sql_server_db.sql_server_db).filter(
                            cntbtch=enpjd.cntbtch,
                            cntitem=enpjd.cntitem

                        ).exclude(notes__regex=r'^\s*$')

                        for eneba in eneba_records:
                            if dry_run:
                                # Just count what would be created
                                exists = Comments.objects.filter(
                                    project=project,
                                    batchnbr=glpost.batchnbr,
                                    entrynbr=glpost.entrynbr,
                                    text=eneba.notes
                                ).exists()
                                if not exists:
                                    synced_count += 1
                            else:
                                # Actually create the comment
                                admin = CustomUser.objects.get(username='sysadmin')
                                comment, created = Comments.objects.get_or_create(
                                    project=project,
                                    batchnbr=glpost.batchnbr,
                                    entrynbr=glpost.entrynbr,
                                    text=eneba.notes,
                                    user= admin,
                                    defaults={

                                        'source': 'SQL Server Reference',
                                        'timestamp': datetime.datetime.now()
                                    }
                                )

                                if created:
                                    synced_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error syncing transaction {glpost.batchnbr}-{glpost.entrynbr}: {str(e)}')
                    )
                    continue

        return synced_count
