from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.tenancy.models import Clinic


class InventoryItem(models.Model):
    class Category(models.TextChoices):
        MEDICATION = "medication", "Medication"
        SUPPLY = "supply", "Supplies"
        FOOD = "food", "Food"
        OTHER = "other", "Other"

    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="inventory_items")

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64)

    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    unit = models.CharField(max_length=50)

    stock_on_hand = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    low_stock_threshold = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    is_active = models.BooleanField(default=True)

    # Nullable to avoid forced defaults when migrating existing data.
    # The API should set this (see viewset perform_create).
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="created_inventory_items",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["clinic", "sku"], name="uniq_inventory_sku_per_clinic"),
        ]
        indexes = [
            models.Index(fields=["clinic", "name"]),
            models.Index(fields=["clinic", "sku"]),
            models.Index(fields=["clinic", "category"]),
            models.Index(fields=["clinic", "stock_on_hand"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"


class InventoryMovement(models.Model):
    class Kind(models.TextChoices):
        IN = "in", "Stock In"
        OUT = "out", "Stock Out"
        ADJUST = "adjust", "Adjustment"

    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="inventory_movements")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")

    kind = models.CharField(max_length=10, choices=Kind.choices)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    note = models.TextField(blank=True)

    # Optional links for later (dispense during appointment / tied to patient)
    patient_id = models.IntegerField(null=True, blank=True)
    appointment_id = models.IntegerField(null=True, blank=True)

    # Same rationale as InventoryItem.created_by
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="created_inventory_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "created_at"]),
            models.Index(fields=["item", "created_at"]),
            models.Index(fields=["clinic", "item", "created_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.clinic_id} | {self.kind} {self.quantity} | {self.item_id} @ "
            f"{timezone.localtime(self.created_at)}"
        )
