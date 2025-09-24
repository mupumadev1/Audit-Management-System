from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import connections, transaction
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging

from main_app.models import DatabaseMapping, Project, SyncLog, ProjectPeriodStats
from transactions.models import SupportingDocument, Glpost

logger = logging.getLogger(__name__)


def _get_aggregated_data(
        sql_server_db: str,
        project_name: str,
        fiscal_year: Optional[str] = None,
        fiscal_period_start: Optional[str] = None,
        fiscal_period_end: Optional[str] = None
) -> Dict:
    """Get aggregated transaction data using SupportingDocument table for supported transactions
    and glpost table for unsupported transactions

    Args:
        sql_server_db: The database alias/name in Django's settings
        project_name: The name of the project to sync
        fiscal_year: Filter by specific fiscal year (e.g., '2024')
        fiscal_period_start: Start of fiscal period range (e.g., '01')
        fiscal_period_end: End of fiscal period range (e.g., '12')

    Returns:
        Dict containing aggregated transaction data
    """
    # Build filter for SupportingDocument queries
    supporting_docs_filter = {'project__project_name': project_name}
    if fiscal_year:
        supporting_docs_filter['fiscal_year'] = fiscal_year
    if fiscal_period_start and fiscal_period_end:
        supporting_docs_filter['fiscal_period__range'] = [fiscal_period_start, fiscal_period_end]
    elif fiscal_period_start:
        supporting_docs_filter['fiscal_period__gte'] = fiscal_period_start
    elif fiscal_period_end:
        supporting_docs_filter['fiscal_period__lte'] = fiscal_period_end

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

    # Get supported transactions directly from SupportingDocument table
    supported_docs = SupportingDocument.objects.filter(
        **supporting_docs_filter,
        supported=True
    )

    supported_count = supported_docs.count()
    supported_value = supported_docs.aggregate(
        total=Sum('transaction_value')
    )['total'] or Decimal('0')

    #print(f"Supported transactions for {project_name} (FY: {fiscal_year}): {supported_count} transactions, ${supported_value}")

    # Get list of supported batch/entry pairs for exclusion from unsupported calculation
    supported_batch_entry_pairs = set(
        SupportingDocument.objects.filter(
            **supporting_docs_filter,
            supported=True
        ).values_list('batchnbr', 'entrynbr').distinct()
    )

    #print(f"Supported batch/entry pairs for exclusion: {supported_batch_entry_pairs}")

    # Calculate unsupported transactions from glpost table using Django ORM
    company_id = mapping.sql_server_db

    # Build base queryset for glpost table
    gl_queryset = Glpost.objects.using(sql_server_db).filter(
        companyid=company_id,
        transamt__gt=0, srceledger='EN'  # Only positive amounts
    )

    # Apply fiscal year filter
    if fiscal_year:
        gl_queryset = gl_queryset.filter(fiscalyr=fiscal_year)

    # Apply fiscal period filters
    if fiscal_period_start and fiscal_period_end:
        gl_queryset = gl_queryset.filter(fiscalperd__range=[fiscal_period_start, fiscal_period_end])
    elif fiscal_period_start:
        gl_queryset = gl_queryset.filter(fiscalperd__gte=fiscal_period_start)
    elif fiscal_period_end:
        gl_queryset = gl_queryset.filter(fiscalperd__lte=fiscal_period_end)

    # Calculate unsupported transactions using composite key exclusion
    if supported_batch_entry_pairs:
        # Get all current transactions with their composite keys
        current_transactions = gl_queryset.values('batchnbr', 'entrynbr', 'acctid', 'fiscalyr',
                                                  'fiscalperd', 'srcecurn', 'srceledger', 'srcetype',
                                                  'postingseq', 'cntdetail', 'transamt')

        # Filter out supported transactions in Python
        unsupported_transaction_keys = []
        unsupported_transaction_amounts = []

        for trans in current_transactions:
            trans_key = (trans['batchnbr'], trans['entrynbr'])
            if trans_key not in supported_batch_entry_pairs:
                # Store the composite primary key for filtering
                unsupported_transaction_keys.append({
                    'acctid': trans['acctid'],
                    'fiscalyr': trans['fiscalyr'],
                    'fiscalperd': trans['fiscalperd'],
                    'srcecurn': trans['srcecurn'],
                    'srceledger': trans['srceledger'],
                    'srcetype': trans['srcetype'],
                    'postingseq': trans['postingseq'],
                    'cntdetail': trans['cntdetail']
                })
                unsupported_transaction_amounts.append(trans['transamt'])

        # Count distinct batch-entry combinations for unsupported transactions
        unsupported_batch_entry_combinations = set()
        unsupported_total_amount = Decimal('0')

        for i, key in enumerate(unsupported_transaction_keys):
            # Find the corresponding transaction to get batch/entry info
            matching_trans = next(
                trans for trans in current_transactions
                if all(trans[k] == v for k, v in key.items())
            )
            unsupported_batch_entry_combinations.add(
                (matching_trans['batchnbr'], matching_trans['entrynbr'])
            )
            unsupported_total_amount += Decimal(str(unsupported_transaction_amounts[i]))

        unsupported_count = len(unsupported_batch_entry_combinations)
        unsupported_value = unsupported_total_amount

    else:
        # If no supported documents, all transactions are unsupported
        # Count distinct batch-entry combinations
        distinct_combinations = gl_queryset.values('batchnbr', 'entrynbr').distinct()
        unsupported_count = distinct_combinations.count()

        # Sum all transaction amounts
        unsupported_value = gl_queryset.aggregate(
            total=Sum('transamt')
        )['total'] or Decimal('0')

    #print(f"Unsupported transactions for {project_name} (FY: {fiscal_year}): {unsupported_count} transactions, ${unsupported_value}")

    return {
        'supported_transactions_number': supported_count,
        'supported_transactions_value': supported_value,
        'unsupported_transactions_number': unsupported_count,
        'unsupported_transactions_value': unsupported_value
    }


class TransactionSyncService:
    def __init__(self):
        self.mysql_db = 'default'  # Your MySQL database alias

    def sync_all_projects(self, use_threading=True, max_workers=5):
        """Sync all projects from all SQL Server databases for all fiscal years and periods"""
        logger.info("Starting comprehensive sync for all projects across all fiscal years and periods")

        # Get all active database mappings
        mappings = DatabaseMapping.objects.filter(is_active=True)

        if use_threading:
            return self._sync_with_threading(mappings, max_workers)
        else:
            return self._sync_sequential(mappings)

    def sync_all_projects_current(self, use_threading=True, max_workers=5):
        """Sync all projects from all SQL Server databases for all fiscal years and periods"""
        logger.info("Starting comprehensive sync for all projects across all fiscal years and periods")

        # Get all active database mappings
        mappings = DatabaseMapping.objects.filter(is_active=True)

        if use_threading:
            return self._sync_with_threading_current(mappings, max_workers)
        else:
            return self._sync_sequential_current(mappings)

    def sync_single_project_comprehensive(self, project_name: str, sql_server_db: str):
        """Sync a single project for all available fiscal years and periods"""
        logger.info(f"Starting comprehensive sync for project {project_name} from {sql_server_db}")

        try:
            # Get all unique fiscal years and periods from supporting documents for this project
            fiscal_combinations = self._get_fiscal_combinations(project_name)

            if not fiscal_combinations:
                logger.warning(f"No fiscal combinations found for project {project_name}")
                return True

            # Start overall sync log
            project_obj = Project.objects.using(self.mysql_db).get(project_name=project_name)
            sync_log = SyncLog.objects.using(self.mysql_db).create(
                project=project_obj,
                status='running',
                sync_started=timezone.now()
            )

            total_records = 0
            successful_periods = 0

            try:
                # Sync each fiscal year/period combination
                for fiscal_year, fiscal_period in fiscal_combinations:
                    try:
                        logger.info(f"Syncing {project_name} for FY {fiscal_year}, Period {fiscal_period}")

                        # Get data for this specific period
                        aggregated_data = _get_aggregated_data(
                            sql_server_db, project_name, fiscal_year, fiscal_period, fiscal_period
                        )
                        # Update ProjectPeriodStats
                        self._update_project_period_stats(
                            project_name, fiscal_year, fiscal_period, aggregated_data
                        )

                        period_total = (aggregated_data['supported_transactions_number'] +
                                        aggregated_data['unsupported_transactions_number'])
                        total_records += period_total
                        successful_periods += 1

                        logger.info(
                            f"Successfully synced {project_name} FY {fiscal_year} Period {fiscal_period}: {period_total} transactions")

                    except Exception as e:
                        logger.error(f"Error syncing {project_name} FY {fiscal_year} Period {fiscal_period}: {str(e)}")
                        continue

                # Update project sync status
                project_obj.last_synced = timezone.now()
                project_obj.sync_status = 'completed'
                project_obj.save(using=self.mysql_db)

                # Update sync log
                sync_log.status = 'completed'
                sync_log.sync_completed = timezone.now()
                sync_log.records_processed = total_records
                sync_log.notes = f"Synced {successful_periods} periods"
                sync_log.save(using=self.mysql_db)

                logger.info(
                    f"Successfully completed comprehensive sync for {project_name}: {total_records} total transactions across {successful_periods} periods")
                return True

            except Exception as e:
                # Update sync log with error
                sync_log.status = 'failed'
                sync_log.error_message = str(e)
                sync_log.save(using=self.mysql_db)

                project_obj.sync_status = 'error'
                project_obj.save(using=self.mysql_db)
                raise

        except Exception as e:
            logger.error(f"Error in comprehensive sync for {project_name}: {str(e)}")
            return False

    def sync_single_project_current_period(self, project_name: str, sql_server_db: str):
        """Sync a single project for the current fiscal year and period only"""
        logger.info(f"Starting comprehensive sync for project {project_name} from {sql_server_db}")

        try:
            # Determine current fiscal year and period based on current date
            now = timezone.now()

            # Example logic for fiscal year and period:
            # Adjust this logic to your actual fiscal calendar if different
            fiscal_year = str(now.year)
            fiscal_period = str(now.month).zfill(2)  # Assuming fiscal period = calendar month

            logger.info(f"Syncing only current fiscal year {fiscal_year} and period {fiscal_period}")

            # Start overall sync log
            project_obj = Project.objects.using(self.mysql_db).get(project_name=project_name)
            sync_log = SyncLog.objects.using(self.mysql_db).create(
                project=project_obj,
                status='running',
                sync_started=timezone.now()
            )

            total_records = 0
            successful_periods = 0

            try:
                logger.info(f"Syncing {project_name} for FY {fiscal_year}, Period {fiscal_period}")

                # Get data for this specific period
                aggregated_data = _get_aggregated_data(
                    sql_server_db, project_name, fiscal_year, fiscal_period, fiscal_period
                )
                print(aggregated_data)
                # Update ProjectPeriodStats
                self._update_project_period_stats(
                    project_name, fiscal_year, fiscal_period, aggregated_data
                )

                period_total = (aggregated_data['supported_transactions_number'] +
                                aggregated_data['unsupported_transactions_number'])
                total_records += period_total
                successful_periods += 1

                logger.info(
                    f"Successfully synced {project_name} FY {fiscal_year} Period {fiscal_period}: {period_total} transactions")

                # Update project sync status
                project_obj.last_synced = timezone.now()
                project_obj.sync_status = 'completed'
                project_obj.save(using=self.mysql_db)

                # Update sync log
                sync_log.status = 'completed'
                sync_log.sync_completed = timezone.now()
                sync_log.records_processed = total_records
                sync_log.notes = f"Synced {successful_periods} period"
                sync_log.save(using=self.mysql_db)

                logger.info(
                    f"Successfully completed comprehensive sync for {project_name}: {total_records} total transactions")
                return True

            except Exception as e:
                # Update sync log with error
                sync_log.status = 'failed'
                sync_log.error_message = str(e)
                sync_log.save(using=self.mysql_db)

                project_obj.sync_status = 'error'
                project_obj.save(using=self.mysql_db)
                raise

        except Exception as e:
            logger.error(f"Error in comprehensive sync for {project_name}: {str(e)}")
            return False

    def _get_fiscal_combinations(self, project_name: str) -> List[Tuple[str, str]]:
        """Get all unique fiscal year/period combinations for a project"""
        """Get all unique fiscal year/period combinations for a project"""
        return list(
            SupportingDocument.objects.filter(project__project_name=project_name)
            .values_list('fiscal_year', 'fiscal_period')
            .distinct()
            .order_by('fiscal_year', 'fiscal_period')
        )

    @transaction.atomic(using='default')
    def _update_project_period_stats(self, project_name: str, fiscal_year: str,
                                     fiscal_period: str, aggregated_data: Dict):
        """Update or create ProjectPeriodStats entry"""

        try:
            project = Project.objects.using(self.mysql_db).get(project_name=project_name)
        except Project.DoesNotExist:
            # Create project if it doesn't exist
            project = Project.objects.using(self.mysql_db).create(
                project_name=project_name,
                description=f'Auto-created for {project_name}'
            )

        # Update or create the period stats
        period_stats, created = ProjectPeriodStats.objects.using(self.mysql_db).update_or_create(
            project=project,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            defaults={
                'supported_transactions_number': aggregated_data['supported_transactions_number'],
                'supported_transactions_value': aggregated_data['supported_transactions_value'],
                'unsupported_transactions_number': aggregated_data['unsupported_transactions_number'],
                'unsupported_transactions_value': aggregated_data['unsupported_transactions_value'],
                'last_calculated': timezone.now()
            }
        )

        action = "Created" if created else "Updated"
        logger.info(f"{action} ProjectPeriodStats for {project_name} FY {fiscal_year} Period {fiscal_period}")

    def _sync_with_threading(self, mappings, max_workers):
        """Sync multiple projects concurrently"""
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit sync tasks
            future_to_mapping = {
                executor.submit(
                    self.sync_single_project_comprehensive,
                    mapping.project_name,
                    mapping.sql_server_db
                ): mapping
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

    def _sync_with_threading_current(self, mappings, max_workers):
        """Sync multiple projects concurrently"""
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit sync tasks
            future_to_mapping = {
                executor.submit(
                    self.sync_single_project_current_period,
                    mapping.project_name,
                    mapping.sql_server_db
                ): mapping
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
            result = self.sync_single_project_comprehensive(
                mapping.project_name,
                mapping.sql_server_db
            )
            results.append({
                'project': mapping.project_name,
                'database': mapping.sql_server_db,
                'success': result
            })

        return results

    def _sync_sequential_current(self, mappings):
        """Sync projects one by one"""
        results = []

        for mapping in mappings:
            result = self.sync_single_project_current_period(
                mapping.project_name,
                mapping.sql_server_db
            )
            results.append({
                'project': mapping.project_name,
                'database': mapping.sql_server_db,
                'success': result
            })

        return results
