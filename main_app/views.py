import logging
from asyncio import as_completed
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone, datetime
from decimal import Decimal
from typing import Dict

from django.db import transaction, connections
from django.shortcuts import render, redirect

from transactions.models import SupportingDocument
from .models import Project, DatabaseMapping, SyncLog  # Import project model
from django.db.models import Sum
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


# Helper functions to check user roles
def is_admin(user):
    return user.is_superuser


def is_staff(user):
    return user.is_staff


# Login view
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_superuser:
                return redirect('main_app:landing_dashboard')
            elif user.is_staff:
                return redirect('main_app:landing_dashboard')
        else:
            return render(request, 'main_app/login.html', {'error': 'Invalid credentials'})
    return render(request, 'main_app/login.html')


# Logout view
def logout_view(request):
    logout(request)
    return redirect('login')


# Admin dashboard view
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Admin-specific data
    context = {
        'message': 'Welcome to the Admin Dashboard',
    }
    return render(request, 'main_app/admin_dashboard.html', context)


# Staff dashboard view
@login_required
@user_passes_test(is_staff)
def staff_dashboard(request):
    # Staff-specific data
    context = {
        'message': 'Welcome to the Staff Dashboard',
    }
    return render(request, 'project_templates/landing_dashboard.html', context)


@login_required
def landing_dashboard(request):
    sync_all_projects()
    """
    View function for the landing dashboard, showing project transaction statistics
    """
    # Get all projects from the database
    projects = Project.objects.all().order_by('-supported_transactions_value')

    # Calculate totals from actual project data
    total_supported_transactions = sum(p.supported_transactions_number for p in projects)
    total_supported_value = sum(p.supported_transactions_value for p in projects)
    total_unsupported_transactions = sum(p.unsupported_transactions_number for p in projects)
    total_unsupported_value = sum(p.unsupported_transactions_value for p in projects)

    # Get top 5 projects by supported transaction value
    top_projects = projects[:5]

    total_projects = projects.count()

    # Prepare data for the dashboard
    context = {
        'total_supported_transactions': total_supported_transactions,
        'total_supported_value': total_supported_value,
        'total_unsupported_transactions': total_unsupported_transactions,
        'total_unsupported_value': total_unsupported_value,
        'top_projects': top_projects,
        'total_projects': total_projects,
    }

    return render(request, 'project_templates/landing_dashboard.html', context)


# Project dashboard view
@login_required
def view_project_dashboard(request):
    projects = Project.objects.all()

    context = {
        'projects': projects,
        # 'summary_data': summary_data, # Pass the summary if calculated here
    }
    return render(request, 'project_templates/view_project_dashboard.html', context)


def _get_aggregated_data(sql_server_db: str, project_name: str) -> Dict:
    """Get aggregated transaction data from a specific SQL Server database

    Args:
        sql_server_db: The database alias/name in Django's settings
        project_name: The name of the project to sync

    Returns:
        Dict containing aggregated transaction data
    """
    # Get supporting documents for this project
    supporting_docs = SupportingDocument.objects.filter(
        project__project_name=project_name
    ).values('batchid', 'supported')

    # Create a mapping of batchid to supported status
    batchid_support_map = {doc['batchid']: doc['supported'] for doc in supporting_docs}
    supported_batchnbrs = [batchid for batchid, supported in batchid_support_map.items() if supported]
    unsupported_batchnbrs = [batchid for batchid, supported in batchid_support_map.items() if not supported]

    # Verify the mapping exists for this project and database
    try:
        mapping = DatabaseMapping.objects.get(
            project_name=project_name,
            sql_server_db=sql_server_db,
            is_active=True
        )
    except DatabaseMapping.DoesNotExist:
        logger.error(f"No active database mapping found for project {project_name} in database {sql_server_db}")
        return {
            'supported_transactions_number': 0,
            'supported_transactions_value': Decimal('0'),
            'unsupported_transactions_number': 0,
            'unsupported_transactions_value': Decimal('0')
        }

    # For this implementation, we assume project_name corresponds to companyid in the glpost table
    database = DatabaseMapping.objects.get(project_name=project_name)
    company_id = database.sql_server_db

    # Build the SQL query
    if supported_batchnbrs or unsupported_batchnbrs:
        # For double-entry accounting, we need to handle the positive and negative entries
        # We'll count distinct batch/entry combinations and sum the absolute values of transactions

        # Build conditions for supported transactions
        if supported_batchnbrs:
            supported_placeholders = ','.join(['%s'] * len(supported_batchnbrs))
            supported_condition = f"batchnbr IN ({supported_placeholders})"
            supported_count_query = f"""
                SELECT COUNT(DISTINCT batchnbr + '-' + entrynbr) 
                FROM glpost 
                WHERE {supported_condition} AND companyid = %s AND transamt > 0
            """
            supported_value_query = f"""
                SELECT SUM(ABS(transamt)) 
                FROM glpost 
                WHERE {supported_condition} AND companyid = %s AND transamt > 0
            """
            supported_params = supported_batchnbrs + [company_id]
            supported_value_params = supported_batchnbrs + [company_id]
        else:
            supported_count_query = "SELECT 0"
            supported_value_query = "SELECT 0"
            supported_params = []
            supported_value_params = []

        # Build conditions for unsupported transactions
        if unsupported_batchnbrs:
            unsupported_placeholders = ','.join(['%s'] * len(unsupported_batchnbrs))
            unsupported_condition = f"batchnbr IN ({unsupported_placeholders})"
            unsupported_count_query = f"""
                SELECT COUNT(DISTINCT batchnbr + '-' + entrynbr) 
                FROM glpost 
                WHERE {unsupported_condition} AND companyid = %s AND transamt > 0
            """
            unsupported_value_query = f"""
                SELECT SUM(ABS(transamt)) 
                FROM glpost 
                WHERE {unsupported_condition} AND companyid = %s AND transamt > 0
            """
            unsupported_params = unsupported_batchnbrs + [company_id]
            unsupported_value_params = unsupported_batchnbrs + [company_id]
        else:
            unsupported_count_query = "SELECT 0"
            unsupported_value_query = "SELECT 0"
            unsupported_params = []
            unsupported_value_params = []

        # Connect to the specific SQL Server database
        connection = connections[sql_server_db]

        supported_count = 0
        supported_value = Decimal('0')
        unsupported_count = 0
        unsupported_value = Decimal('0')

        with connection.cursor() as cursor:
            try:
                # Execute queries and get results
                if supported_params:
                    cursor.execute(supported_count_query, supported_params)
                    supported_count = cursor.fetchone()[0] or 0

                    cursor.execute(supported_value_query, supported_value_params)
                    supported_value = Decimal(str(cursor.fetchone()[0] or 0))

                if unsupported_params:
                    cursor.execute(unsupported_count_query, unsupported_params)
                    unsupported_count = cursor.fetchone()[0] or 0

                    cursor.execute(unsupported_value_query, unsupported_value_params)
                    unsupported_value = Decimal(str(cursor.fetchone()[0] or 0))

                return {
                    'supported_transactions_number': supported_count,
                    'supported_transactions_value': supported_value,
                    'unsupported_transactions_number': unsupported_count,
                    'unsupported_transactions_value': unsupported_value
                }
            except Exception as e:
                logger.error(f"Error querying {sql_server_db} for project {project_name}: {str(e)}")
                return {
                    'supported_transactions_number': 0,
                    'supported_transactions_value': Decimal('0'),
                    'unsupported_transactions_number': 0,
                    'unsupported_transactions_value': Decimal('0')
                }
    else:
        # No supporting documents for this project
        return {
            'supported_transactions_number': 0,
            'supported_transactions_value': Decimal('0'),
            'unsupported_transactions_number': 0,
            'unsupported_transactions_value': Decimal('0')
        }


class TransactionSyncService:
    def __init__(self):
        self.mysql_db = 'default'  # Your MySQL database alias

    def sync_all_projects(self, use_threading=True, max_workers=5):
        """Sync all projects from all SQL Server databases"""
        logger.info("Starting sync for all projects")

        # Get all active database mappings
        mappings = DatabaseMapping.objects.filter(is_active=True)

        if use_threading:
            return self._sync_with_threading(mappings, max_workers)
        else:
            return self._sync_sequential(mappings)

    def sync_single_project(self, project_name: str, sql_server_db: str):
        """Sync a single project from a specific SQL Server database"""
        logger.info(f"Syncing project {project_name} from {sql_server_db}")

        try:
            # Get aggregated data from SQL Server
            aggregated_data = _get_aggregated_data(sql_server_db, project_name)

            # Update MySQL with aggregated data
            self._update_project_data(project_name, aggregated_data)

            logger.info(f"Successfully synced {project_name}")
            return True

        except Exception as e:
            logger.error(f"Error syncing {project_name}: {str(e)}")
            return False

    def _sync_with_threading(self, mappings, max_workers):
        """Sync multiple projects concurrently"""
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit sync tasks
            future_to_mapping = {
                executor.submit(self.sync_single_project, mapping.project_name, mapping.sql_server_db): mapping
                for mapping in mappings
            }

            # Process completed tasks
            for future in as_completed(future_to_mapping):
                mapping = future_to_mapping[future]
                try:
                    result = future.result()
                    results.append({
                        'project': mapping.project_name,
                        'database': mapping.sql_server_db,
                        'success': result
                    })
                except Exception as e:
                    logger.error(f"Exception for {mapping.project_name}: {str(e)}")
                    results.append({
                        'project': mapping.project_name,
                        'database': mapping.sql_server_db,
                        'success': False,
                        'error': str(e)
                    })

        return results

    def _sync_sequential(self, mappings):
        """Sync projects one by one"""
        results = []

        for mapping in mappings:
            result = self.sync_single_project(mapping.project_name, mapping.sql_server_db)
            results.append({
                'project': mapping.project_name,
                'database': mapping.sql_server_db,
                'success': result
            })

        return results

    @transaction.atomic(using='default')
    def _update_project_data(self, project_name: str, aggregated_data: Dict):
        """Update project data in MySQL database"""

        # Start sync log
        project, created = Project.objects.using(self.mysql_db).get_or_create(
            project_name=project_name,
            defaults={'description': f'Auto-created for {project_name}'}
        )

        sync_log = SyncLog.objects.using(self.mysql_db).create(
            project=project,
            status='running'
        )

        try:
            # Update project with new data
            project.supported_transactions_number = aggregated_data['supported_transactions_number']
            project.supported_transactions_value = aggregated_data['supported_transactions_value']
            project.unsupported_transactions_number = aggregated_data['unsupported_transactions_number']
            project.unsupported_transactions_value = aggregated_data['unsupported_transactions_value']
            project.last_synced = datetime.now()
            project.sync_status = 'completed'
            project.save(using=self.mysql_db)

            # Update sync log
            sync_log.status = 'completed'
            sync_log.sync_completed = datetime.now()
            sync_log.records_processed = (
                    aggregated_data['supported_transactions_number'] +
                    aggregated_data['unsupported_transactions_number']
            )
            sync_log.save(using=self.mysql_db)

            logger.info(f"Updated project {project_name} with {sync_log.records_processed} transactions")

        except Exception as e:
            # Update sync log with error
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save(using=self.mysql_db)

            project.sync_status = 'error'
            project.save(using=self.mysql_db)

            raise

    def get_sync_status(self) -> Dict:
        """Get overall sync status"""
        projects = Project.objects.using(self.mysql_db).all()

        status = {
            'total_projects': projects.count(),
            'completed': projects.filter(sync_status='completed').count(),
            'pending': projects.filter(sync_status='pending').count(),
            'in_progress': projects.filter(sync_status='in_progress').count(),
            'error': projects.filter(sync_status='error').count(),
            'last_sync_times': {}
        }

        # Get last sync times for each project
        for project in projects:
            status['last_sync_times'][project.project_name] = project.last_synced

        return status
