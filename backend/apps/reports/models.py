from django.conf import settings
from django.db import models

from apps.tenancy.models import Clinic


class ReportExportJob(models.Model):
    class ReportType(models.TextChoices):
        REVENUE_SUMMARY = "revenue_summary", "Revenue Summary"
        REMINDER_ANALYTICS = "reminder_analytics", "Reminder Analytics"
        CANCELLATION_ANALYTICS = "cancellation_analytics", "Cancellation Analytics"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="report_export_jobs",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_report_exports",
    )
    report_type = models.CharField(max_length=64, choices=ReportType.choices)
    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    file_name = models.CharField(max_length=255, blank=True)
    file_content = models.TextField(blank=True)
    content_type = models.CharField(max_length=64, default="text/csv")
    error = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["clinic", "status", "created_at"],
                name="reports_rep_clinic__676dc9_idx",
            ),
            models.Index(
                fields=["clinic", "report_type", "created_at"],
                name="reports_rep_clinic__c811cf_idx",
            ),
        ]

    def __str__(self):
        return f"ReportExportJob({self.report_type}, {self.status}, clinic={self.clinic_id})"
