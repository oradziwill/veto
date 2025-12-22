from rest_framework import serializers

from .models import MedicalRecord


class MedicalRecordReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        fields = [
            "id",
            "appointment",
            "subjective",
            "objective",
            "assessment",
            "plan",
            "weight_kg",
            "temperature_c",
            "created_by",
            "created_at",
            "updated_at",
        ]


class MedicalRecordWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        fields = [
            "appointment",
            "subjective",
            "objective",
            "assessment",
            "plan",
            "weight_kg",
            "temperature_c",
        ]
