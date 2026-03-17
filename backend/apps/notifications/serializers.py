from __future__ import annotations

from rest_framework import serializers

from .models import Notification


class NotificationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "clinic",
            "kind",
            "title",
            "body",
            "link_tab",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields
