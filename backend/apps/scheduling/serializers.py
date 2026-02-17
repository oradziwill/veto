from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.patients.serializers import PatientReadSerializer, VetMiniSerializer
from apps.scheduling.models import Appointment, HospitalStay


class AppointmentReadSerializer(serializers.ModelSerializer):
    patient = PatientReadSerializer(read_only=True)
    vet = VetMiniSerializer(read_only=True)

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
            "visit_type",
            "starts_at",
            "ends_at",
            "status",
            "reason",
            "internal_notes",
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
