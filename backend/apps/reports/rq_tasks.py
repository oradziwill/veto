"""
RQ worker tasks and enqueue helpers for reports.
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def report_export_job_task(job_id: int) -> None:
    """RQ entrypoint: process one export job by primary key."""
    from apps.reports.job_runner import execute_report_export_job_by_id

    execute_report_export_job_by_id(job_id)


def try_enqueue_report_export_job(job_id: int) -> None:
    """
    Push a new export job to the default RQ queue when enabled in settings.

    Failures are logged; the job stays ``pending`` for cron / process-pending.
    """
    if not getattr(settings, "RQ_REPORT_EXPORT_ENQUEUE", False):
        return
    try:
        import django_rq

        django_rq.get_queue("default").enqueue(report_export_job_task, job_id)
    except Exception:
        logger.exception("Failed to enqueue report export job %s", job_id)
