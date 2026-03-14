from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.tenancy.models import Clinic


class Reminder(models.Model):
    class ReminderType(models.TextChoices):
        APPOINTMENT = "appointment", "Appointment"
        VACCINATION = "vaccination", "Vaccination"
        INVOICE = "invoice", "Invoice"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="reminders",
    )
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reminders",
    )
    appointment = models.ForeignKey(
        "scheduling.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reminders",
    )
    vaccination = models.ForeignKey(
        "medical.Vaccination",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reminders",
    )
    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reminders",
    )

    reminder_type = models.CharField(max_length=20, choices=ReminderType.choices)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)

    recipient = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)

    scheduled_for = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_for", "id"]
        indexes = [
            models.Index(fields=["clinic", "status", "scheduled_for"]),
            models.Index(fields=["clinic", "reminder_type", "status"]),
            models.Index(fields=["clinic", "channel", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.reminder_type}:{self.channel}:{self.status} ({self.clinic_id})"
