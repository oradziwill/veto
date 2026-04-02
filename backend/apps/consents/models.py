from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic


class ConsentDocument(models.Model):
    """
    Owner consent for a procedure, tied to a visit (appointment).
    Binary files live in S3; this row stores metadata and a frozen payload for hashing/PDF.
    """

    class DocumentType(models.TextChoices):
        PROCEDURE = "procedure_consent", "Procedure consent"

    class Status(models.TextChoices):
        PENDING_SIGNATURE = "pending_signature", "Pending signature"
        SIGNED = "signed", "Signed"

    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="consent_documents")
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="consent_documents",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="consent_documents",
    )

    document_type = models.CharField(
        max_length=32,
        choices=DocumentType.choices,
        default=DocumentType.PROCEDURE,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_SIGNATURE,
        db_index=True,
    )
    template_version = models.CharField(max_length=16, default="1")

    payload_snapshot = models.JSONField(
        help_text="Frozen fields used to render PDF and content_hash."
    )
    content_hash = models.CharField(max_length=64, db_index=True)

    job_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    final_pdf_s3_key = models.CharField(max_length=1024, blank=True)
    signature_png_s3_key = models.CharField(max_length=1024, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_consent_documents",
    )
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="signed_consent_documents",
    )
    location_label = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional workstation label, e.g. reception or exam room.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "appointment", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"ConsentDocument({self.id}, {self.status}, appointment={self.appointment_id})"
