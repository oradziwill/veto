from rest_framework import serializers
from .models import Patient
from apps.clients.serializers import ClientSerializer
from apps.accounts.serializers import MeSerializer


class PatientSerializer(serializers.ModelSerializer):
    owner = ClientSerializer(read_only=True)
    owner_id = serializers.IntegerField(write_only=True, required=False)
    primary_vet = MeSerializer(read_only=True)
    primary_vet_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Patient
        fields = [
            "id",
            "clinic",
            "owner",
            "owner_id",
            "name",
            "species",
            "breed",
            "sex",
            "birth_date",
            "microchip_no",
            "allergies",
            "notes",
            "primary_vet",
            "primary_vet_id",
            "created_at",
        ]
        read_only_fields = ["clinic", "created_at"]


