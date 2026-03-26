from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "clinic",
            "actor",
            "actor_username",
            "request_id",
            "action",
            "entity_type",
            "entity_id",
            "before",
            "after",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
