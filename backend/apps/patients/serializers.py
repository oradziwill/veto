from rest_framework import serializers

from apps.accounts.models import User
from apps.clients.models import Client
from apps.medical.models import PatientHistoryEntry
from apps.patients.models import Patient


class PatientHistoryForPatientSerializer(serializers.ModelSerializer):
    """Serializer for patient history list in PatientDetailsModal (frontend expects visit_date, created_by_name, etc.)."""

    visit_date = serializers.DateTimeField(source="created_at", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    appointment = serializers.SerializerMethodField()
    receipt_summary = serializers.SerializerMethodField()

    class Meta:
        model = PatientHistoryEntry
        fields = [
            "id",
            "visit_date",
            "created_at",
            "note",
            "receipt_summary",
            "appointment",
            "created_by_name",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name or ''} {obj.created_by.last_name or ''}".strip() or obj.created_by.username
        return None

    def get_appointment(self, obj):
        return None

    def get_receipt_summary(self, obj):
        return ""


class ClientMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "first_name", "last_name", "phone", "email"]


class VetMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "is_vet"]


class PatientReadSerializer(serializers.ModelSerializer):
    owner = ClientMiniSerializer()
    primary_vet = VetMiniSerializer(allow_null=True)

    class Meta:
        model = Patient
        fields = "__all__"


class PatientWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = [
            "owner",
            "name",
            "species",
            "breed",
            "sex",
            "birth_date",
            "microchip_no",
            "allergies",
            "notes",
            "primary_vet",
        ]
