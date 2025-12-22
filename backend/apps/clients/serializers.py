from rest_framework import serializers
from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='__str__', read_only=True)
    
    class Meta:
        model = Client
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "email",
            "created_at",
        ]
        read_only_fields = ["created_at"]

