from rest_framework import serializers

from apps.patients.models import Patient
from apps.clients.models import Client
from apps.accounts.models import User


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
