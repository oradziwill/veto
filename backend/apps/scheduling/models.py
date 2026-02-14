from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.patients.models import Patient
from apps.tenancy.models import Clinic

from .models_exceptions import VetAvailabilityException  # noqa: F401


class Appointment(models.Model):
    class VisitType(models.TextChoices):
        OUTPATIENT = "outpatient", "Outpatient"
        HOSPITALIZATION = "hospitalization", "Hospitalization"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked-in"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No-show"

    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="appointments")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="appointments")
    vet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
        limit_choices_to={"is_vet": True},
    )

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    visit_type = models.CharField(
        max_length=20,
        choices=VisitType.choices,
        default=VisitType.OUTPATIENT,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    reason = models.CharField(max_length=255, blank=True)
    internal_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [
            models.Index(fields=["clinic", "starts_at"]),
            models.Index(fields=["vet", "starts_at"]),
            models.Index(fields=["patient", "starts_at"]),
        ]

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "ends_at must be after starts_at"})

        if self.patient_id and self.clinic_id and self.patient.clinic_id != self.clinic_id:
            raise ValidationError({"patient": "Patient clinic must match appointment clinic."})

        if (
            self.vet_id
            and self.clinic_id
            and getattr(self.vet, "clinic_id", None) != self.clinic_id
        ):
            raise ValidationError({"vet": "Vet clinic must match appointment clinic."})

        if self.vet_id and self.clinic_id and self.starts_at and self.ends_at:
            qs = Appointment.objects.filter(
                clinic_id=self.clinic_id,
                vet_id=self.vet_id,
            ).exclude(status=Appointment.Status.CANCELLED)

            if self.pk:
                qs = qs.exclude(pk=self.pk)

            qs = qs.filter(starts_at__lt=self.ends_at, ends_at__gt=self.starts_at)

            if qs.exists():
                raise ValidationError(
                    "This vet already has an overlapping appointment in this time range."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        start = timezone.localtime(self.starts_at).strftime("%Y-%m-%d %H:%M")
        return f"{self.clinic} | {start} | {self.patient} | {self.vet}"


class HospitalStay(models.Model):
    """Pet hospitalization - in-patient stay at clinic hospital."""

    class Status(models.TextChoices):
        ADMITTED = "admitted", "Admitted"
        DISCHARGED = "discharged", "Discharged"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="hospital_stays",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="hospital_stays",
    )
    attending_vet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="hospital_stays",
        limit_choices_to={"is_vet": True},
    )
    admission_appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hospital_stays",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ADMITTED,
    )
    reason = models.CharField(max_length=255, blank=True)
    cage_or_room = models.CharField(max_length=64, blank=True)
    admitted_at = models.DateTimeField()
    discharged_at = models.DateTimeField(null=True, blank=True)
    discharge_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-admitted_at"]
        indexes = [
            models.Index(fields=["clinic", "status"]),
            models.Index(fields=["patient", "admitted_at"]),
        ]

    def __str__(self) -> str:
        return f"HospitalStay {self.patient} @ {self.clinic} ({self.status})"


# Register additional scheduling models kept in separate modules
from .models_working_hours import VetWorkingHours  # noqa: E402,F401
