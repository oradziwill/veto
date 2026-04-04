from apps.tenancy.models import Clinic
from django.conf import settings
from django.db import models


class WebhookEventType(models.TextChoices):
    """Audit-aligned action names this system may emit to integrations."""

    PORTAL_APPOINTMENT_BOOKED = "portal_appointment_booked", "Portal appointment booked"
    PORTAL_APPOINTMENT_CANCELLED = (
        "portal_appointment_cancelled",
        "Portal appointment cancelled",
    )
    PORTAL_BOOKING_DEPOSIT_PAID = "portal_booking_deposit_paid", "Portal booking deposit paid"
    INVOICE_PAYMENT_RECORDED = "invoice_payment_recorded", "Invoice payment recorded"


class WebhookSubscription(models.Model):
    """
    Staff-configured HTTPS endpoint that receives JSON POSTs for selected events.
    """

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="webhook_subscriptions",
    )
    target_url = models.URLField(max_length=2048)
    description = models.CharField(max_length=255, blank=True)
    secret = models.CharField(
        max_length=256,
        blank=True,
        help_text="If set, HMAC-SHA256 hex of the raw JSON body is sent as X-Veto-Webhook-Signature.",
    )
    event_types = models.JSONField(
        default=list,
        help_text="List of event type strings (see WebhookEventType).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_webhook_subscriptions",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["clinic", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"WebhookSubscription({self.clinic_id}, {self.target_url[:48]})"


class WebhookDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    subscription = models.ForeignKey(
        WebhookSubscription,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    event_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["subscription", "status", "created_at"]),
        ]
