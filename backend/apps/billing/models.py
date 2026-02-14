"""
Billing models for the veterinary clinic.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.clients.models import Client
from apps.inventory.models import InventoryItem
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic


class Service(models.Model):
    """
    Catalog of billable services (consultation, vaccination, surgery, etc.).
    """

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="services",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=64, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["clinic", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.clinic})"


class Invoice(models.Model):
    """
    Invoice billed to a client. Linked to optional appointment.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        CANCELLED = "cancelled", "Cancelled"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="PLN")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "status"]),
            models.Index(fields=["clinic", "client"]),
            models.Index(fields=["clinic", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Invoice #{self.id} - {self.client} ({self.status})"

    @property
    def total(self) -> Decimal:
        return sum(
            (line.line_total for line in self.lines.all()),
            Decimal("0"),
        )

    @property
    def amount_paid(self) -> Decimal:
        return sum(
            (p.amount for p in self.payments.filter(status="completed")),
            Decimal("0"),
        )

    @property
    def balance_due(self) -> Decimal:
        return self.total - self.amount_paid


class InvoiceLine(models.Model):
    """
    Single line on an invoice (service, product, or custom charge).
    """

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_lines",
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_lines",
    )

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.description} x{self.quantity} @ {self.unit_price}"

    @property
    def line_total(self) -> Decimal:
        return self.quantity * self.unit_price


class Payment(models.Model):
    """
    Payment recorded against an invoice.
    """

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        TRANSFER = "transfer", "Bank Transfer"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
    )
    paid_at = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=128, blank=True)
    note = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]
        indexes = [
            models.Index(fields=["invoice"]),
        ]

    def __str__(self) -> str:
        return f"{self.amount} {self.method} for Invoice #{self.invoice_id}"
