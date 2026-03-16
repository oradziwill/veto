from __future__ import annotations

from django.conf import settings
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
    experiment_key = models.CharField(max_length=64, blank=True)
    experiment_variant = models.CharField(max_length=32, default="control")

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
            models.Index(fields=["clinic", "experiment_key", "experiment_variant"]),
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
    locale = models.CharField(max_length=10, default="en")
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


class ReminderTemplate(models.Model):
    class Locale(models.TextChoices):
        EN = "en", "English"
        PL = "pl", "Polski"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="reminder_templates",
    )
    reminder_type = models.CharField(max_length=20, choices=Reminder.ReminderType.choices)
    channel = models.CharField(max_length=10, choices=Reminder.Channel.choices)
    locale = models.CharField(max_length=10, choices=Locale.choices, default=Locale.EN)
    is_active = models.BooleanField(default=True)
    subject_template = models.CharField(max_length=255, blank=True)
    body_template = models.TextField()
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_reminder_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "reminder_type", "channel", "locale"],
                name="reminders_template_clinic_type_channel_locale_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["clinic", "reminder_type", "channel", "locale", "is_active"])
        ]

    def __str__(self) -> str:
        return (
            f"ReminderTemplate(clinic={self.clinic_id}, type={self.reminder_type}, "
            f"channel={self.channel}, locale={self.locale})"
        )


class ReminderTemplateVersion(models.Model):
    template = models.ForeignKey(
        ReminderTemplate,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.PositiveIntegerField()
    subject_template = models.CharField(max_length=255, blank=True)
    body_template = models.TextField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reminder_template_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["template", "version"],
                name="reminders_template_version_uniq",
            )
        ]
        ordering = ["-version", "-created_at"]

    def __str__(self) -> str:
        return f"ReminderTemplateVersion(template={self.template_id}, version={self.version})"


class ReminderProviderConfig(models.Model):
    class EmailProvider(models.TextChoices):
        INTERNAL = "internal", "Internal"
        SENDGRID = "sendgrid", "SendGrid"

    class SmsProvider(models.TextChoices):
        INTERNAL = "internal", "Internal"
        TWILIO = "twilio", "Twilio"

    clinic = models.OneToOneField(
        Clinic,
        on_delete=models.CASCADE,
        related_name="reminder_provider_config",
    )
    email_provider = models.CharField(
        max_length=20,
        choices=EmailProvider.choices,
        default=EmailProvider.INTERNAL,
    )
    sms_provider = models.CharField(
        max_length=20,
        choices=SmsProvider.choices,
        default=SmsProvider.INTERNAL,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_reminder_provider_configs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["clinic", "email_provider", "sms_provider"])]

    def __str__(self) -> str:
        return (
            f"ReminderProviderConfig(clinic={self.clinic_id}, email={self.email_provider}, "
            f"sms={self.sms_provider})"
        )
