from rest_framework import serializers
from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            "id",
            "clinic",
            "patient",
            "vet",
            "starts_at",
            "ends_at",
            "status",
            "reason",
            "internal_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["clinic", "created_at", "updated_at"]
