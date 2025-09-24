# Celery task for scheduled sync
from celery import shared_task
import logging
from main_app.services import TransactionSyncService
logger = logging.getLogger(__name__)


@shared_task
def scheduled_sync_transactions():
    """Celery task for scheduled transaction sync"""
    logger.info("Starting scheduled transaction sync")

    service = TransactionSyncService()
    results = service.sync_all_projects(use_threading=True, max_workers=5)

    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful

    logger.info(f"Scheduled sync completed: {successful} successful, {failed} failed")

    return {
        'successful': successful,
        'failed': failed,
        'results': results
    }
