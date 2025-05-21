import logging
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta

from main_app.models import *

logger = logging.getLogger(__name__)


class SyncMonitor:
    def __init__(self):
        self.alert_thresholds = {
            'max_sync_age_minutes': 30,  # Alert if sync hasn't run in 30 minutes
            'max_failure_rate': 0.2,  # Alert if >20% of syncs fail
            'max_consecutive_failures': 3  # Alert after 3 consecutive failures
        }

    def check_sync_health(self):
        """Check overall sync health and send alerts if needed"""
        issues = []

        # Check for stale syncs
        stale_projects = self._check_stale_syncs()
        if stale_projects:
            issues.append(f"Stale syncs: {', '.join(stale_projects)}")

        # Check failure rate
        high_failure_projects = self._check_failure_rates()
        if high_failure_projects:
            issues.append(f"High failure rate: {', '.join(high_failure_projects)}")

        # Check consecutive failures
        consecutive_failures = self._check_consecutive_failures()
        if consecutive_failures:
            issues.append(f"Consecutive failures: {', '.join(consecutive_failures)}")

        if issues:
            self._send_alert("\n".join(issues))

        return len(issues) == 0

    def _check_stale_syncs(self):
        """Check for projects that haven't synced recently"""
        threshold = datetime.now() - timedelta(minutes=self.alert_thresholds['max_sync_age_minutes'])

        stale_projects = Project.objects.filter(
            last_synced__lt=threshold
        ).values_list('project_name', flat=True)

        return list(stale_projects)

    def _check_failure_rates(self):
        """Check for projects with high failure rates"""
        high_failure_projects = []

        # Check last 24 hours
        since = datetime.now() - timedelta(hours=24)

        for project in Project.objects.all():
            logs = SyncLog.objects.filter(
                project=project,
                sync_started__gte=since
            )

            if logs.count() > 5:  # Only check if enough samples
                failure_rate = logs.filter(status='failed').count() / logs.count()
                if failure_rate > self.alert_thresholds['max_failure_rate']:
                    high_failure_projects.append(project.project_name)

        return high_failure_projects

    def _check_consecutive_failures(self):
        """Check for projects with consecutive failures"""
        consecutive_failure_projects = []

        for project in Project.objects.all():
            # Get last N sync logs
            recent_logs = SyncLog.objects.filter(
                project=project
            ).order_by('-sync_started')[:self.alert_thresholds['max_consecutive_failures']]

            if (len(recent_logs) >= self.alert_thresholds['max_consecutive_failures'] and
                    all(log.status == 'failed' for log in recent_logs)):
                consecutive_failure_projects.append(project.project_name)

        return consecutive_failure_projects

    def _send_alert(self, message):
        """Send alert notification"""
        subject = "Transaction Sync Alert"
        full_message = f"""
        Transaction sync issues detected:

        {message}

        Time: {datetime.now()}

        Please check the sync logs for more details.
        """

        try:
            send_mail(
                subject,
                full_message,
                settings.DEFAULT_FROM_EMAIL,
                settings.SYNC_ALERT_EMAILS,
                fail_silently=False
            )
            logger.info("Sync alert email sent successfully")
        except Exception as e:
            logger.error(f"Failed to send sync alert email: {str(e)}")

    def get_sync_metrics(self):
        """Get comprehensive sync metrics"""
        return {
            'total_projects': Project.objects.count(),
            'projects_synced_today': Project.objects.filter(
                last_synced__date=datetime.now().date()
            ).count(),
            'projects_with_errors': Project.objects.filter(
                sync_status='error'
            ).count(),
            'avg_sync_time': self._calculate_avg_sync_time(),
            'sync_frequency_by_project': self._get_sync_frequencies()
        }

    def _calculate_avg_sync_time(self):
        """Calculate average sync time"""
        completed_logs = SyncLog.objects.filter(
            status='completed',
            sync_completed__isnull=False
        )

        if not completed_logs:
            return None

        total_time = sum(
            (log.sync_completed - log.sync_started).total_seconds()
            for log in completed_logs
        )

        return total_time / completed_logs.count()

    def _get_sync_frequencies(self):
        """Get sync frequency per project"""
        frequencies = {}

        for project in Project.objects.all():
            last_week = datetime.now() - timedelta(days=7)
            sync_count = SyncLog.objects.filter(
                project=project,
                sync_started__gte=last_week
            ).count()

            frequencies[project.project_name] = sync_count

        return frequencies


