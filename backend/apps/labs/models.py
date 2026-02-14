"""
Lab integration: in-clinic and external labs, orders, results.
"""

from django.conf import settings
from django.db import models

from apps.patients.models import Patient
from apps.scheduling.models import Appointment, HospitalStay
from apps.tenancy.models import Clinic


class Lab(models.Model):
    """Lab provider - in-clinic or external."""

    class LabType(models.TextChoices):
        IN_CLINIC = "in_clinic", "In-Clinic"
        EXTERNAL = "external", "External"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="labs",
        null=True,
        blank=True,
        help_text="Null for external labs used by multiple clinics",
    )
    name = models.CharField(max_length=255)
    lab_type = models.CharField(
        max_length=20,
        choices=LabType.choices,
        default=LabType.IN_CLINIC,
    )
    address = models.CharField(max_length=512, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["clinic"]), models.Index(fields=["lab_type"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_lab_type_display()})"


class LabTest(models.Model):
    """Catalog of lab test types."""

    lab = models.ForeignKey(
        Lab,
        on_delete=models.CASCADE,
        related_name="tests",
        null=True,
        blank=True,
        help_text="Null = test available at any lab",
    )
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=32, blank=True)
    reference_range = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["lab"]), models.Index(fields=["code"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class LabOrder(models.Model):
    """Order for lab tests - sent to in-clinic or external lab."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="lab_orders",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="lab_orders",
    )
    lab = models.ForeignKey(
        Lab,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    clinical_notes = models.TextField(blank=True)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_orders",
    )
    hospital_stay = models.ForeignKey(
        HospitalStay,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_orders",
    )

    ordered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_orders_created",
    )
    ordered_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-ordered_at"]
        indexes = [
            models.Index(fields=["clinic", "status"]),
            models.Index(fields=["patient"]),
        ]

    def __str__(self) -> str:
        return f"LabOrder #{self.id} {self.patient} @ {self.lab} ({self.status})"


class LabOrderLine(models.Model):
    """Single test requested in a lab order."""

    order = models.ForeignKey(
        LabOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    test = models.ForeignKey(
        LabTest,
        on_delete=models.PROTECT,
        related_name="order_lines",
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("order", "test")]
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.order} - {self.test}"


class LabResult(models.Model):
    """Result for a single test in a lab order."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    order_line = models.OneToOneField(
        LabOrderLine,
        on_delete=models.CASCADE,
        related_name="result",
    )
    value = models.CharField(max_length=255, blank=True)
    value_numeric = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    unit = models.CharField(max_length=32, blank=True)
    reference_range = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lab_results_entered",
    )

    class Meta:
        ordering = ["order_line__test__name"]

    def __str__(self) -> str:
        return f"LabResult {self.order_line.test} = {self.value or self.value_numeric}"
