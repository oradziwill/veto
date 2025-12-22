from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.patients.models import Patient
from apps.tenancy.models import Clinic


class Appointment(models.Model):
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
        # Time sanity
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "ends_at must be after starts_at"})

        # Clinic consistency
        if self.patient_id and self.clinic_id and self.patient.clinic_id != self.clinic_id:
            raise ValidationError({"patient": "Patient clinic must match appointment clinic."})

        if (
            self.vet_id
            and self.clinic_id
            and getattr(self.vet, "clinic_id", None) != self.clinic_id
        ):
            raise ValidationError({"vet": "Vet clinic must match appointment clinic."})

        # Overlap prevention (MVP): no overlapping appointments for the same vet in the same clinic,
        # ignoring CANCELLED appointments.
        if self.vet_id and self.clinic_id and self.starts_at and self.ends_at:
            qs = Appointment.objects.filter(
                clinic_id=self.clinic_id,
                vet_id=self.vet_id,
            ).exclude(status=Appointment.Status.CANCELLED)

            if self.pk:
                qs = qs.exclude(pk=self.pk)

            # overlap condition: existing.starts < new.ends AND existing.ends > new.starts
            qs = qs.filter(starts_at__lt=self.ends_at, ends_at__gt=self.starts_at)

            if qs.exists():
                raise ValidationError(
                    "This vet already has an overlapping appointment in this time range."
                )

    def save(self, *args, **kwargs):
        # Ensure model validation runs on save (Admin + API)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        start = timezone.localtime(self.starts_at).strftime("%Y-%m-%d %H:%M")
        return f"{self.clinic} | {start} | {self.patient} | {self.vet}"
