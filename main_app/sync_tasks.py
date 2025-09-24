import time
import logging
import threading
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
# Add these missing imports:
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore

from audit_management_system.settings import SYNC_CONFIG
from main_app.models import SyncMetrics
from main_app.services import TransactionSyncService  # Your service import

# Configure logger
logger = logging.getLogger(__name__)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")

def start_scheduler():
    """Start the scheduler if not already running"""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started successfully")

def send_alert_notification(subject, message):
    """Send alert notification - implement based on your needs"""
    try:
        from django.core.mail import send_mail
        send_mail(
            subject=f"Transaction Sync Alert: {subject}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[SYNC_CONFIG['ALERT_EMAIL']],
            fail_silently=True,
        )
        logger.info(f"Alert sent: {subject}")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")


def check_consecutive_failures():
    """Check if we have too many consecutive failures"""
    try:
        recent_syncs = SyncMetrics.objects.filter(
            started_at__gte=timezone.now() - timedelta(hours=2)
        ).order_by('-started_at')[:SYNC_CONFIG['MAX_CONSECUTIVE_FAILURES']]

        if len(recent_syncs) >= SYNC_CONFIG['MAX_CONSECUTIVE_FAILURES']:
            if all(sync.status in ['failed', 'skipped'] for sync in recent_syncs):
                return True
    except Exception as e:
        logger.error(f"Error checking consecutive failures: {e}")

    return False


@scheduler.scheduled_job(
    'interval',
    minutes=SYNC_CONFIG['INTERVAL_MINUTES'],
    id='sync_transactions'
)
def sync_transactions():
    """
    Enhanced scheduled transaction sync with:
    - Exception handling
    - Overlap prevention
    - Performance monitoring
    - Failure tracking
    - Alerting
    """
    lock_key = 'sync_transactions_lock'
    start_time = time.time()
    start_timestamp = timezone.now()
    sync_metric = None

    # Check if sync is already running
    if cache.get(lock_key):
        logger.warning("Sync already running, skipping this execution")

        # Create skipped metric record
        SyncMetrics.objects.create(
            started_at=start_timestamp,
            completed_at=timezone.now(),
            status='skipped',
            error_message='Previous sync still running'
        )

        return {
            'status': 'skipped',
            'reason': 'already_running',
            'timestamp': start_timestamp.isoformat()
        }

    try:
        # Set lock (longer than expected execution time)
        cache.set(lock_key, True, timeout=SYNC_CONFIG['LOCK_TIMEOUT_MINUTES'] * 60)

        # Create initial metric record
        sync_metric = SyncMetrics.objects.create(
            started_at=start_timestamp,
            status='running'
        )

        logger.info("Starting scheduled transaction sync")

        # Check for consecutive failures before proceeding
        if check_consecutive_failures():
            error_msg = "Too many consecutive sync failures detected"
            logger.error(error_msg)
            send_alert_notification(
                "Consecutive Sync Failures",
                f"{error_msg}. Please check the system immediately."
            )

        # Execute the actual sync
        service = TransactionSyncService()
        results = service.sync_all_projects(
            use_threading=True,
            max_workers=SYNC_CONFIG['MAX_WORKERS']
        )

        # Calculate metrics
        successful = sum(1 for r in results if r.get('success', False))
        failed = len(results) - successful
        execution_time = time.time() - start_time

        # Log results
        logger.info(
            f"Scheduled sync completed in {execution_time:.2f}s: "
            f"{successful} successful, {failed} failed out of {len(results)} total"
        )

        # Log failed projects for debugging
        if failed > 0:
            failed_projects = [
                r.get('project_id', 'unknown')
                for r in results
                if not r.get('success', False)
            ]
            logger.warning(f"Failed projects: {failed_projects[:10]}")  # Limit to first 10

            # Send alert if failure rate is high
            failure_rate = failed / len(results) if results else 0
            if failure_rate > 0.5:  # More than 50% failures
                send_alert_notification(
                    "High Sync Failure Rate",
                    f"Sync completed with {failure_rate:.1%} failure rate. "
                    f"{failed} out of {len(results)} projects failed."
                )

        # Update metric record
        sync_metric.completed_at = timezone.now()
        sync_metric.execution_time = execution_time
        sync_metric.successful_count = successful
        sync_metric.failed_count = failed
        sync_metric.total_projects = len(results)
        sync_metric.status = 'completed'
        sync_metric.save()

        # Performance warning
        if execution_time > SYNC_CONFIG['TIMEOUT_MINUTES'] * 60 * 0.8:  # 80% of timeout
            logger.warning(
                f"Sync took {execution_time:.2f}s, approaching timeout limit of "
                f"{SYNC_CONFIG['TIMEOUT_MINUTES']} minutes"
            )

        return {
            'status': 'completed',
            'successful': successful,
            'failed': failed,
            'total': len(results),
            'execution_time': execution_time,
            'failure_rate': failed / len(results) if results else 0,
            'timestamp': start_timestamp.isoformat(),
            'results': results[:5] if len(results) > 5 else results  # Limit results size
        }

    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = f"Critical error in scheduled sync: {str(e)}"

        logger.error(error_msg, exc_info=True)

        # Update metric record with error
        if sync_metric:
            sync_metric.completed_at = timezone.now()
            sync_metric.execution_time = execution_time
            sync_metric.status = 'failed'
            sync_metric.error_message = str(e)
            sync_metric.save()

        # Send critical error alert
        send_alert_notification(
            "Critical Sync Error",
            f"{error_msg}\n\nExecution time: {execution_time:.2f}s\n\n"
            f"Please investigate immediately."
        )

        return {
            'status': 'failed',
            'error': str(e),
            'execution_time': execution_time,
            'timestamp': start_timestamp.isoformat()
        }

    finally:
        # Always release the lock
        cache.delete(lock_key)
        logger.debug("Sync lock released")


def get_sync_health_status():
    """
    Get the current health status of the sync process
    Returns: dict with status and details
    """
    try:
        # Get latest sync
        latest_sync = SyncMetrics.objects.first()

        if not latest_sync:
            return {
                'status': 'unknown',
                'reason': 'no_sync_history',
                'last_sync': None
            }

        current_time = timezone.now()
        expected_interval = timedelta(minutes=SYNC_CONFIG['INTERVAL_MINUTES'])
        time_since_last = current_time - latest_sync.started_at

        # Check if sync is overdue
        if time_since_last > expected_interval * 2:  # 2x the interval
            return {
                'status': 'unhealthy',
                'reason': 'sync_overdue',
                'last_sync': latest_sync.started_at.isoformat(),
                'overdue_by_minutes': int(time_since_last.total_seconds() / 60)
            }

        # Check recent failure rate
        recent_syncs = SyncMetrics.objects.filter(
            started_at__gte=current_time - timedelta(hours=1),
            status__in=['completed', 'failed']
        )

        if recent_syncs.exists():
            failed_count = recent_syncs.filter(status='failed').count()
            total_count = recent_syncs.count()
            failure_rate = failed_count / total_count

            if failure_rate > 0.5:
                return {
                    'status': 'degraded',
                    'reason': 'high_failure_rate',
                    'failure_rate': f"{failure_rate:.1%}",
                    'last_sync': latest_sync.started_at.isoformat()
                }

        # Check if current sync is running too long
        if latest_sync.status == 'running':
            running_time = current_time - latest_sync.started_at
            if running_time > timedelta(minutes=SYNC_CONFIG['TIMEOUT_MINUTES']):
                return {
                    'status': 'unhealthy',
                    'reason': 'sync_timeout',
                    'running_for_minutes': int(running_time.total_seconds() / 60),
                    'last_sync': latest_sync.started_at.isoformat()
                }

        return {
            'status': 'healthy',
            'last_sync': latest_sync.started_at.isoformat(),
            'last_status': latest_sync.status,
            'recent_success_rate': f"{((latest_sync.successful_count or 0) / max(latest_sync.total_projects or 1, 1)):.1%}"
        }

    except Exception as e:
        logger.error(f"Error checking sync health: {e}")
        return {
            'status': 'error',
            'reason': 'health_check_failed',
            'error': str(e)
        }

