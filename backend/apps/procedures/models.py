from __future__ import annotations

import uuid

from django.db import models


class ClinicalProcedure(models.Model):
    class Category(models.TextChoices):
        DERMATOLOGY = "dermatology", "Dermatologia"
        GASTROENTEROLOGY = "gastroenterology", "Gastroenterologia"
        CARDIOLOGY = "cardiology", "Kardiologia"
        NEUROLOGY = "neurology", "Neurologia"
        INTERNAL_MEDICINE = "internal_medicine", "Interna"
        PREVENTIVE_CARE = "preventive_care", "Medycyna zapobiegawcza"
        EMERGENCY = "emergency", "Nagłe przypadki"
        UROLOGY = "urology", "Urologia"
        ORTHOPEDICS = "orthopedics", "Ortopedia"
        ONCOLOGY = "oncology", "Onkologia"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=50, choices=Category.choices)
    species = models.JSONField(default=list)
    entry_node_id = models.CharField(max_length=100)
    nodes = models.JSONField()
    tags = models.JSONField(default=list, blank=True)
    source = models.TextField(blank=True)
    last_reviewed = models.DateField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class VisitProcedureSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        "scheduling.Appointment",
        on_delete=models.CASCADE,
        related_name="procedure_sessions",
        null=True,
        blank=True,
    )
    procedure = models.ForeignKey(
        ClinicalProcedure,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    doctor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="procedure_sessions",
    )
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="procedure_sessions",
    )
    path = models.JSONField(default=list)
    collected_data = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    result_node_id = models.CharField(max_length=100, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.procedure.name} — {self.patient}"
