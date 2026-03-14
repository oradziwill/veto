from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.clients.models import Client
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
        DEFERRED = "deferred", "Deferred"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Provider(models.TextChoices):
        INTERNAL = "internal", "Internal"
        SENDGRID = "sendgrid", "SendGrid"
        TWILIO = "twilio", "Twilio"

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
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.INTERNAL)
    provider_message_id = models.CharField(max_length=255, blank=True)
    provider_status = models.CharField(max_length=64, blank=True)

    recipient = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)

    scheduled_for = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    last_error = models.TextField(blank=True)
    last_webhook_payload = models.JSONField(default=dict, blank=True)

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


class ReminderPreference(models.Model):
    class PreferredChannel(models.TextChoices):
        AUTO = "auto", "Auto"
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="reminder_preferences",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="reminder_preferences",
    )
    allow_email = models.BooleanField(default=True)
    allow_sms = models.BooleanField(default=False)
    preferred_channel = models.CharField(
        max_length=10,
        choices=PreferredChannel.choices,
        default=PreferredChannel.AUTO,
    )
    timezone = models.CharField(max_length=64, default="UTC")
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "client"],
                name="reminders_pref_clinic_client_uniq",
            )
        ]
        indexes = [models.Index(fields=["clinic", "client"])]

    def __str__(self) -> str:
        return f"ReminderPreference(client={self.client_id}, clinic={self.clinic_id})"


class ReminderEvent(models.Model):
    class EventType(models.TextChoices):
        ENQUEUED = "enqueued", "Enqueued"
        DEFERRED = "deferred", "Deferred"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        WEBHOOK_UPDATE = "webhook_update", "Webhook update"

    reminder = models.ForeignKey(
        Reminder,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["reminder", "event_type"])]

    def __str__(self) -> str:
        return f"ReminderEvent(reminder={self.reminder_id}, type={self.event_type})"
