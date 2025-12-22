from rest_framework import serializers
<<<<<<< HEAD
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

=======
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
>>>>>>> 6510c5a53af801136dfb834a4f1b5a7dc1afb1f4
