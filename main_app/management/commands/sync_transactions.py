from django.core.management.base import BaseCommand

from main_app.services import TransactionSyncService


class Command(BaseCommand):
    help = 'Sync transaction data from SQL Server databases to MySQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project',
            type=str,
            help='Sync specific project only'
        )
        parser.add_argument(
            '--database',
            type=str,
            help='Sync from specific SQL Server database only'
        )
        parser.add_argument(
            '--threads',
            type=int,
            default=5,
            help='Number of concurrent threads to use'
        )
        parser.add_argument(
            '--no-threading',
            action='store_true',
            help='Disable threading and run sequentially'
        )

    def handle(self, *args, **options):
        service = TransactionSyncService()

        self.stdout.write("Starting sync for all projects...")
        use_threading = not options['no_threading']

        results = service.sync_all_projects(
            use_threading=use_threading,
            max_workers=options['threads']
        )

        # Report results
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful

        self.stdout.write(
            self.style.SUCCESS(f"Sync completed: {successful} successful, {failed} failed")
        )

        # Show failed projects
        if failed > 0:
            self.stdout.write("\nFailed projects:")
            for result in results:
                if not result['success']:
                    self.stdout.write(
                        self.style.ERROR(f"  - {result['project']} ({result['database']})")
                    )
