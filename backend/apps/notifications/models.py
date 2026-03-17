from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.tenancy.models import Clinic


class Notification(models.Model):
    class Kind(models.TextChoices):
        APPOINTMENT_CONFIRMED = "appointment_confirmed", "Appointment confirmed"
        RESCHEDULE_REQUEST = "reschedule_request", "Reschedule request"
        ESCALATION_TRIGGERED = "escalation_triggered", "Escalation triggered"
        INVOICE_OVERDUE = "invoice_overdue", "Invoice overdue"
        LOW_STOCK = "low_stock", "Low stock"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    kind = models.CharField(max_length=40, choices=Kind.choices)
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=500)
    link_tab = models.CharField(max_length=64, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
            models.Index(fields=["clinic", "kind", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Notification(recipient={self.recipient_id}, kind={self.kind}, read={self.is_read})"
