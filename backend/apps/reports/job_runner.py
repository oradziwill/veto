"""
Synchronous runner for a single report export job (DB row).

Used by management commands, admin API batch processing, and RQ workers.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.reports.models import ReportExportJob
from apps.reports.services import build_report_csv


def execute_report_export_job_by_id(job_id: int) -> str:
    """
    Claim a pending job (skip_locked) and generate CSV.

    Returns one of: ``processed``, ``failed``, ``skipped``.
    """
    with transaction.atomic():
        job = (
            ReportExportJob.objects.select_for_update(skip_locked=True)
            .filter(pk=job_id, status=ReportExportJob.Status.PENDING)
            .first()
        )
        if not job:
            return "skipped"
        job.status = ReportExportJob.Status.PROCESSING
        job.error = ""
        job.save(update_fields=["status", "error", "updated_at"])

    job.refresh_from_db()
    try:
        file_name, content = build_report_csv(job)
        job.file_name = file_name
        job.file_content = content
        job.status = ReportExportJob.Status.COMPLETED
        job.completed_at = timezone.now()
        job.save(
            update_fields=[
                "file_name",
                "file_content",
                "status",
                "completed_at",
                "updated_at",
            ]
        )
        return "processed"
    except Exception as exc:
        job.status = ReportExportJob.Status.FAILED
        job.error = str(exc)
        job.save(update_fields=["status", "error", "updated_at"])
        return "failed"
