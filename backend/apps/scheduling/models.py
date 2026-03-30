import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.patients.models import Patient
from apps.tenancy.models import Clinic

from .models_clinic_hours import ClinicWorkingHours  # noqa: F401
from .models_duty import DutyAssignment  # noqa: F401
from .models_exceptions import VetAvailabilityException  # noqa: F401


class Room(models.Model):
    """Clinic room for visits (e.g. Room 1, RTG room). Admin configures rooms per clinic."""

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    name = models.CharField(max_length=64)
    display_order = models.PositiveSmallIntegerField(
        default=0, help_text="Order in lists (lower first)"
    )

    class Meta:
        ordering = ["display_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "name"], name="scheduling_room_clinic_name_uniq"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.clinic}: {self.name}"


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

    class CancelledBy(models.TextChoices):
        CLIENT = "client", "Client"
        CLINIC = "clinic", "Clinic"

    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="appointments")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="appointments")
    vet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
        limit_choices_to={"is_vet": True},
    )
    room = models.ForeignKey(
        "Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
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
    cancellation_reason = models.CharField(max_length=255, blank=True)
    cancelled_by = models.CharField(
        max_length=20,
        choices=CancelledBy.choices,
        blank=True,
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    portal_deposit_invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_deposit_appointments",
    )

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

        if self.room_id and self.clinic_id and self.room.clinic_id != self.clinic_id:
            raise ValidationError({"room": "Room must belong to the appointment clinic."})

        if self.room_id and self.clinic_id and self.starts_at and self.ends_at:
            room_qs = Appointment.objects.filter(
                clinic_id=self.clinic_id,
                room_id=self.room_id,
            ).exclude(status=Appointment.Status.CANCELLED)
            if self.pk:
                room_qs = room_qs.exclude(pk=self.pk)
            room_qs = room_qs.filter(starts_at__lt=self.ends_at, ends_at__gt=self.starts_at)
            if room_qs.exists():
                raise ValidationError(
                    "This room already has an overlapping appointment in this time range."
                )

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


class HospitalStayNote(models.Model):
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="hospital_stay_notes",
    )
    hospital_stay = models.ForeignKey(
        HospitalStay,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    note_type = models.CharField(max_length=40, blank=True, default="round")
    note = models.TextField()
    vitals = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hospital_stay_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["clinic", "hospital_stay", "-created_at"],
                name="scheduli_hospita_1a2f2c_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"HospitalStayNote(stay={self.hospital_stay_id})"


class HospitalStayTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="hospital_stay_tasks",
    )
    hospital_stay = models.ForeignKey(
        HospitalStay,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_hospital_stay_tasks",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_hospital_stay_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "due_at", "id"]
        indexes = [
            models.Index(
                fields=["clinic", "hospital_stay", "status"],
                name="scheduli_hospita_0c0f9a_idx",
            ),
            models.Index(
                fields=["clinic", "due_at"],
                name="scheduli_hospita_8c7856_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"HospitalStayTask(stay={self.hospital_stay_id}, status={self.status})"


class HospitalMedicationOrder(models.Model):
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="hospital_medication_orders",
    )
    hospital_stay = models.ForeignKey(
        HospitalStay,
        on_delete=models.CASCADE,
        related_name="medication_orders",
    )
    medication_name = models.CharField(max_length=255)
    dose = models.DecimalField(max_digits=8, decimal_places=2)
    dose_unit = models.CharField(max_length=32, default="mg")
    route = models.CharField(max_length=32, blank=True, default="")
    frequency_hours = models.PositiveSmallIntegerField(default=8)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_hospital_medication_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["clinic", "hospital_stay", "is_active"],
                name="scheduli_hospita_7740cc_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"HospitalMedicationOrder(stay={self.hospital_stay_id}, med={self.medication_name})"


class HospitalMedicationAdministration(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        GIVEN = "given", "Given"
        SKIPPED = "skipped", "Skipped"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="hospital_medication_administrations",
    )
    medication_order = models.ForeignKey(
        HospitalMedicationOrder,
        on_delete=models.CASCADE,
        related_name="administrations",
    )
    scheduled_for = models.DateTimeField(null=True, blank=True)
    administered_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    administered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hospital_medication_administrations",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_for", "-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["clinic", "status", "scheduled_for"],
                name="scheduli_hospita_7d2ec2_idx",
            ),
            models.Index(
                fields=["clinic", "medication_order"],
                name="scheduli_hospita_91e80a_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"HospitalMedicationAdministration(order={self.medication_order_id}, status={self.status})"


class HospitalDischargeSummary(models.Model):
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="hospital_discharge_summaries",
    )
    hospital_stay = models.OneToOneField(
        HospitalStay,
        on_delete=models.CASCADE,
        related_name="discharge_summary",
    )
    diagnosis = models.TextField(blank=True)
    hospitalization_course = models.TextField(blank=True)
    procedures = models.TextField(blank=True)
    medications_on_discharge = models.JSONField(default=list, blank=True)
    home_care_instructions = models.TextField(blank=True)
    warning_signs = models.TextField(blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_discharge_summaries",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(
                fields=["clinic", "hospital_stay"],
                name="scheduli_hospita_13ef93_idx",
            ),
            models.Index(
                fields=["clinic", "-updated_at"],
                name="scheduli_hospita_9126f4_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"HospitalDischargeSummary(stay={self.hospital_stay_id})"


class WaitingQueueEntry(models.Model):
    """Walk-in patient queue. Receptionist/doctor adds patients; doctor calls them."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"
        LEFT = "left", "Left"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="queue_entries",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="queue_entries",
    )
    chief_complaint = models.CharField(max_length=255, blank=True)
    is_urgent = models.BooleanField(default=False)
    position = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    arrived_at = models.DateTimeField(auto_now_add=True)
    called_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="called_patients",
    )
    appointment = models.OneToOneField(
        "Appointment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="queue_entry",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["position", "arrived_at"]

    def __str__(self) -> str:
        return f"Queue#{self.position} {self.patient} @ {self.clinic} ({self.status})"


class VisitRecording(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.PROTECT,
        related_name="visit_recordings",
    )
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="visit_recordings",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_visit_recordings",
    )

    job_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    original_filename = models.CharField(max_length=512)
    content_type = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADED,
        db_index=True,
    )
    last_error = models.TextField(blank=True)

    input_s3_key = models.CharField(max_length=1024, blank=True)
    transcript = models.TextField(blank=True)
    summary_text = models.TextField(blank=True)
    summary_structured = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "status"]),
            models.Index(fields=["appointment", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"VisitRecording({self.id}, appointment={self.appointment_id}, status={self.status})"


# Register additional scheduling models kept in separate modules
from .models_working_hours import VetWorkingHours  # noqa: E402,F401
