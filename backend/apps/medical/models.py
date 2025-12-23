from django.conf import settings
from django.db import models

from apps.patients.models import Patient
from apps.scheduling.models import Appointment


class MedicalRecord(models.Model):
    """
    SOAP clinical note attached 1:1 to an appointment.
    """

    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.PROTECT,
        related_name="medical_record",
    )

    # SOAP
    subjective = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    plan = models.TextField(blank=True)

    # Vitals
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_medical_records",
        limit_choices_to={"is_vet": True},
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"MedicalRecord #{self.pk} for Appointment #{self.appointment_id}"


class PatientHistoryEntry(models.Model):
    """
    Simple visit history / timeline entry for a patient.

    - Can optionally link to an appointment (recommended).
    - Always scoped to a clinic (tenant safety).
    - Created by a vet.
    """

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="history_entries",
    )

    clinic = models.ForeignKey(
        "tenancy.Clinic",
        on_delete=models.PROTECT,
        related_name="patient_history_entries",
    )

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.PROTECT,
        related_name="history_entries",
        null=True,
        blank=True,
    )

    note = models.TextField()
    receipt_summary = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_patient_history_entries",
        limit_choices_to={"is_vet": True},
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "patient", "created_at"]),
            models.Index(fields=["clinic", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"PatientHistoryEntry #{self.pk} for Patient #{self.patient_id}"
