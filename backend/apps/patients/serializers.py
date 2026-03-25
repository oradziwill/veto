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
    services_performed = serializers.SerializerMethodField()

    class Meta:
        model = PatientHistoryEntry
        fields = [
            "id",
            "visit_date",
            "created_at",
            "note",
            "receipt_summary",
            "appointment",
            "invoice",
            "services_performed",
            "created_by_name",
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return (
                f"{obj.created_by.first_name or ''} {obj.created_by.last_name or ''}".strip()
                or obj.created_by.username
            )
        return None

    def get_appointment(self, obj):
        appointment = getattr(obj, "appointment", None)
        if not appointment:
            return None
        return {
            "id": appointment.id,
            "starts_at": appointment.starts_at.isoformat(),
            "ends_at": appointment.ends_at.isoformat(),
            "status": appointment.status,
        }

    def get_receipt_summary(self, obj):
        services = self.get_services_performed(obj)
        if not services:
            return ""
        parts = [f"{line['description']} x{line['quantity']}" for line in services]
        return ", ".join(parts)

    def get_services_performed(self, obj):
        invoice = getattr(obj, "invoice", None)
        if not invoice:
            return []
        lines = getattr(invoice, "lines", None)
        if lines is None:
            return []
        return [
            {
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
            }
            for line in lines.all()
        ]


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
