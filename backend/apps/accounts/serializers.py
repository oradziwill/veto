from rest_framework import serializers
from .models import User


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "is_vet",
            "clinic",
            "is_staff",
            "is_superuser",
        ]


class VetSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]
