from apps.patients.serializers import PatientReadSerializer
from apps.scheduling.models import Appointment
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.patients.serializers import PatientReadSerializer
from apps.scheduling.models import Appointment


class AppointmentReadSerializer(serializers.ModelSerializer):
    patient = PatientReadSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = "__all__"


class AppointmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "patient",
            "vet",
            "starts_at",
            "ends_at",
            "status",
            "reason",
            "internal_notes",
        ]

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
