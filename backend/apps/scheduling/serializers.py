from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.patients.serializers import PatientReadSerializer, VetMiniSerializer
from apps.scheduling.models import (
    Appointment,
    HospitalDischargeSummary,
    HospitalMedicationAdministration,
    HospitalMedicationOrder,
    HospitalStay,
    HospitalStayNote,
    HospitalStayTask,
    Room,
    VisitRecording,
    WaitingQueueEntry,
)


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "name", "display_order"]


class AppointmentReadSerializer(serializers.ModelSerializer):
    patient = PatientReadSerializer(read_only=True)
    vet = VetMiniSerializer(read_only=True)
    room = RoomSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Appointment
        fields = "__all__"


class AppointmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "vet",
            "room",
            "visit_type",
            "starts_at",
            "ends_at",
            "status",
            "reason",
            "internal_notes",
            "cancellation_reason",
            "cancelled_by",
            "cancelled_at",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        starts_at = attrs.get("starts_at")
        ends_at = attrs.get("ends_at")

        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "ends_at must be after starts_at"})

        try:
            # Run model-level validation (overlaps, clinic consistency, etc.)
            instance = Appointment(**attrs)
            instance.clean()
        except DjangoValidationError as e:
            # Field-level errors from Django
            if hasattr(e, "message_dict"):
                raise serializers.ValidationError(e.message_dict) from e

            # Non-field errors fallback
            raise serializers.ValidationError({"non_field_errors": e.messages}) from e

        return attrs


class HospitalStayReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalStay
        fields = "__all__"


class HospitalStayWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalStay
        fields = [
            "patient",
            "attending_vet",
            "admission_appointment",
            "reason",
            "cage_or_room",
            "admitted_at",
        ]

    def validate_patient(self, value):
        request = self.context.get("request")
        if request and value.clinic_id != getattr(request.user, "clinic_id", None):
            raise serializers.ValidationError("Patient must belong to your clinic.")
        return value

    def validate_attending_vet(self, value):
        request = self.context.get("request")
        if request and getattr(value, "clinic_id", None) != getattr(
            request.user, "clinic_id", None
        ):
            raise serializers.ValidationError("Vet must belong to your clinic.")
        return value


class HospitalStayNoteReadSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name() or obj.created_by.username

    class Meta:
        model = HospitalStayNote
        fields = "__all__"


class HospitalStayNoteWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalStayNote
        fields = ["note_type", "note", "vitals"]


class HospitalStayTaskReadSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    completed_by_name = serializers.SerializerMethodField()

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name() or obj.created_by.username

    def get_completed_by_name(self, obj):
        if not obj.completed_by:
            return None
        return obj.completed_by.get_full_name() or obj.completed_by.username

    class Meta:
        model = HospitalStayTask
        fields = "__all__"


class HospitalStayTaskWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalStayTask
        fields = [
            "title",
            "description",
            "priority",
            "status",
            "due_at",
        ]


class HospitalMedicationOrderReadSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name() or obj.created_by.username

    class Meta:
        model = HospitalMedicationOrder
        fields = "__all__"


class HospitalMedicationOrderWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalMedicationOrder
        fields = [
            "medication_name",
            "dose",
            "dose_unit",
            "route",
            "frequency_hours",
            "starts_at",
            "ends_at",
            "instructions",
            "is_active",
        ]


class HospitalMedicationAdministrationReadSerializer(serializers.ModelSerializer):
    administered_by_name = serializers.SerializerMethodField()

    def get_administered_by_name(self, obj):
        if not obj.administered_by:
            return None
        return obj.administered_by.get_full_name() or obj.administered_by.username

    class Meta:
        model = HospitalMedicationAdministration
        fields = "__all__"


class HospitalMedicationAdministrationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalMedicationAdministration
        fields = [
            "scheduled_for",
            "administered_at",
            "status",
            "note",
        ]


class HospitalDischargeSummaryReadSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.SerializerMethodField()

    def get_generated_by_name(self, obj):
        if not obj.generated_by:
            return None
        return obj.generated_by.get_full_name() or obj.generated_by.username

    class Meta:
        model = HospitalDischargeSummary
        fields = "__all__"


class HospitalDischargeSummaryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalDischargeSummary
        fields = [
            "diagnosis",
            "hospitalization_course",
            "procedures",
            "medications_on_discharge",
            "home_care_instructions",
            "warning_signs",
            "follow_up_date",
        ]


class WaitingQueueEntryReadSerializer(serializers.ModelSerializer):
    patient = PatientReadSerializer(read_only=True)
    called_by = VetMiniSerializer(read_only=True)

    class Meta:
        model = WaitingQueueEntry
        fields = "__all__"


class WaitingQueueEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaitingQueueEntry
        fields = ["patient", "chief_complaint", "is_urgent", "notes"]


class VisitRecordingSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitRecording
        fields = [
            "id",
            "job_id",
            "clinic",
            "appointment",
            "uploaded_by",
            "original_filename",
            "content_type",
            "size_bytes",
            "status",
            "last_error",
            "input_s3_key",
            "transcript",
            "summary_text",
            "summary_structured",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class VisitRecordingUploadResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitRecording
        fields = ["id", "job_id", "status", "input_s3_key", "created_at"]
