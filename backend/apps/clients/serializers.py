from rest_framework import serializers
from .models import Client, ClientClinic


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "first_name", "last_name", "phone", "email", "created_at"]
        read_only_fields = ["created_at"]


class ClientClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientClinic
        fields = ["id", "client", "clinic", "notes", "is_active", "created_at"]
        read_only_fields = ["created_at"]
