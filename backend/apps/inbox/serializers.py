from __future__ import annotations

from rest_framework import serializers

from apps.inbox.models import InboxTask


class InboxTaskSerializer(serializers.ModelSerializer):
    vet_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    closed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InboxTask
        fields = [
            "id",
            "vet",
            "vet_name",
            "task_type",
            "patient_name",
            "note",
            "status",
            "created_by",
            "created_by_name",
            "created_at",
            "closed_by",
            "closed_by_name",
            "closed_at",
            "close_comment",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "closed_by",
            "closed_at",
            "updated_at",
        ]

    def get_vet_name(self, obj):
        if obj.vet:
            return f"{obj.vet.first_name} {obj.vet.last_name}".strip() or obj.vet.username
        return None

    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
        return None

    def get_closed_by_name(self, obj):
        if obj.closed_by:
            return f"{obj.closed_by.first_name} {obj.closed_by.last_name}".strip() or obj.closed_by.username
        return None
