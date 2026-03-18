from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic


class IngestionDocument(models.Model):
    class DocumentType(models.TextChoices):
        TREATMENT_HISTORY = "treatment_history", "Treatment history"
        LAB_OUTCOME = "lab_outcome", "Lab outcome"
        OTHER = "other", "Other"

    class Source(models.TextChoices):
        MANUAL_UPLOAD = "manual_upload", "Manual upload"
        API_INGEST = "api_ingest", "API ingest"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="ingestion_documents",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="ingestion_documents",
    )
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingestion_documents",
    )
    lab_order = models.ForeignKey(
        "labs.LabOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingestion_documents",
    )

    document_type = models.CharField(
        max_length=32,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    source = models.CharField(
        max_length=32,
        choices=Source.choices,
        default=Source.MANUAL_UPLOAD,
    )

    job_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    original_filename = models.CharField(max_length=512)
    content_type = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADED,
        db_index=True,
    )
    input_s3_key = models.CharField(max_length=1024, blank=True)
    output_html_s3_key = models.CharField(max_length=1024, blank=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_ingestion_documents",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "status"]),
            models.Index(fields=["clinic", "patient", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"IngestionDocument({self.id}, job_id={self.job_id}, status={self.status})"
