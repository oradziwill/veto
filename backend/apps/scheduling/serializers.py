from rest_framework import serializers

from .models import Appointment


class AppointmentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = "__all__"


class AppointmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "patient",
            "vet",
            "start_at",
            "end_at",
            "reason",
            "notes",
            "status",
        ]

    def validate(self, attrs):
        """
        Prevent overlapping appointments for the same vet.
        Assumes model has start_at and end_at DateTimeFields.
        """
        start_at = attrs.get("start_at")
        end_at = attrs.get("end_at")
        vet = attrs.get("vet")

        if start_at and end_at and start_at >= end_at:
            raise serializers.ValidationError("end_at must be after start_at.")

        # If vet or times are missing, skip overlap check (serializer-level)
        if not (vet and start_at and end_at):
            return attrs

        qs = Appointment.objects.filter(vet=vet)

        # When updating, exclude current instance
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        # Overlap condition:
        # existing.start < new.end AND existing.end > new.start
        qs = qs.filter(start_at__lt=end_at, end_at__gt=start_at)

        if qs.exists():
            raise serializers.ValidationError("Vet already has an appointment in this time range.")

        return attrs
