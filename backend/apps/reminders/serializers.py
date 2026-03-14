from __future__ import annotations

from rest_framework import serializers

from .models import Reminder


class ReminderReadSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.name", read_only=True)
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = Reminder
        fields = [
            "id",
            "clinic",
            "patient",
            "patient_name",
            "owner_name",
            "appointment",
            "vaccination",
            "invoice",
            "reminder_type",
            "channel",
            "status",
            "recipient",
            "subject",
            "body",
            "scheduled_for",
            "sent_at",
            "attempts",
            "max_attempts",
            "last_error",
            "created_at",
            "updated_at",
        ]

    def get_owner_name(self, obj):
        owner = getattr(getattr(obj, "patient", None), "owner", None)
        if not owner:
            return ""
        return f"{owner.first_name} {owner.last_name}".strip()
