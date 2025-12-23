from rest_framework import serializers

from .models import MedicalRecord, PatientHistoryEntry


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


class PatientHistoryEntryReadSerializer(serializers.ModelSerializer):
    """
    Frontend-friendly shape:
    - visit_date prefers appointment.starts_at when appointment exists
    - include created_by basic identity
    """

    visit_date = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PatientHistoryEntry
        fields = [
            "id",
            "patient",
            "clinic",
            "appointment",
            "visit_date",
            "note",
            "receipt_summary",
            "created_by",
            "created_by_name",
            "created_at",
        ]

    def get_visit_date(self, obj):
        if obj.appointment_id and obj.appointment and obj.appointment.starts_at:
            return obj.appointment.starts_at.isoformat()
        return obj.created_at.isoformat()

    def get_created_by_name(self, obj):
        u = obj.created_by
        full = f"{(u.first_name or '').strip()} {(u.last_name or '').strip()}".strip()
        return full or u.username


class PatientHistoryEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientHistoryEntry
        fields = [
            "appointment",
            "note",
            "receipt_summary",
        ]
