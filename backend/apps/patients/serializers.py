from rest_framework import serializers
<<<<<<< HEAD
from .models import Patient
from apps.clients.serializers import ClientSerializer
from apps.accounts.serializers import MeSerializer


class PatientSerializer(serializers.ModelSerializer):
    owner = ClientSerializer(read_only=True)
    owner_id = serializers.IntegerField(write_only=True, required=False)
    primary_vet = MeSerializer(read_only=True)
    primary_vet_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
=======
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

>>>>>>> 6510c5a53af801136dfb834a4f1b5a7dc1afb1f4
    class Meta:
        model = Patient
        fields = [
            "id",
            "clinic",
            "owner",
<<<<<<< HEAD
            "owner_id",
=======
>>>>>>> 6510c5a53af801136dfb834a4f1b5a7dc1afb1f4
            "name",
            "species",
            "breed",
            "sex",
            "birth_date",
            "microchip_no",
            "allergies",
            "notes",
            "primary_vet",
<<<<<<< HEAD
            "primary_vet_id",
            "created_at",
        ]
        read_only_fields = ["clinic", "created_at"]


=======
            "created_at",
        ]


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
>>>>>>> 6510c5a53af801136dfb834a4f1b5a7dc1afb1f4
