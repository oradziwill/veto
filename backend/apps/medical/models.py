from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.tenancy.models import Clinic


class MedicalRecord(models.Model):
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="medical_records",
        related_query_name="medical_record",
    )
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="medical_records",
    )

    # partner-owned; keep as-is
    ai_summary = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_medical_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["clinic", "patient"])]

    def __str__(self) -> str:
        return f"MedicalRecord({self.patient_id})"


class PatientHistoryEntry(models.Model):
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="patient_history_entries",
        related_query_name="patient_history_entry",
    )
    record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name="history_entries",
    )
    appointment = models.ForeignKey(
        "scheduling.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patient_history_entries",
    )
    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patient_history_entries",
    )
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_patient_history_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "record", "-created_at"]),
            models.Index(fields=["clinic", "appointment", "-created_at"]),
            models.Index(fields=["clinic", "invoice", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"HistoryEntry({self.record_id})"


class ClinicalExam(models.Model):
    # IMPORTANT: different related_name than MedicalRecord
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="clinical_exams",
        related_query_name="clinical_exam",
    )

    appointment = models.OneToOneField(
        "scheduling.Appointment",
        on_delete=models.CASCADE,
        related_name="clinical_exam",
    )

    initial_notes = models.TextField(blank=True)
    clinical_examination = models.TextField(blank=True)

    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    heart_rate_bpm = models.PositiveIntegerField(null=True, blank=True)
    respiratory_rate_rpm = models.PositiveIntegerField(null=True, blank=True)

    additional_notes = models.TextField(blank=True)
    owner_instructions = models.TextField(blank=True)
    initial_diagnosis = models.TextField(blank=True)
    transcript = models.TextField(blank=True)
    ai_notes_raw = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_clinical_exams",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["clinic", "appointment"])]

    def __str__(self) -> str:
        return f"ClinicalExam(appt={self.appointment_id})"


class Prescription(models.Model):
    """Prescription linked to a patient and optionally to a visit (MedicalRecord)."""

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="prescriptions",
    )
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="prescriptions",
    )
    appointment = models.ForeignKey(
        "scheduling.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prescriptions",
    )
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prescriptions_for_record",
    )
    prescribed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prescribed_prescriptions",
    )
    drug_name = models.CharField(max_length=200, blank=True)
    dosage = models.CharField(max_length=200, blank=True)
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "patient"], name="medical_pre_clinic__9a8b7c_idx")
        ]

    def __str__(self) -> str:
        return f"Prescription(patient={self.patient_id})"


class Vaccination(models.Model):
    """Vaccination record: vaccine given to a patient, when, and when next dose is due."""

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="vaccinations",
    )
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="vaccinations",
    )
    vaccine_name = models.CharField(max_length=200)
    batch_number = models.CharField(max_length=100, blank=True)
    administered_at = models.DateField()
    next_due_at = models.DateField(null=True, blank=True)
    administered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="administered_vaccinations",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-administered_at"]
        indexes = [
            models.Index(fields=["clinic", "patient"], name="medical_vac_clinic__a1b2c3_idx")
        ]

    def __str__(self) -> str:
        return f"Vaccination(patient={self.patient_id}, {self.vaccine_name})"
