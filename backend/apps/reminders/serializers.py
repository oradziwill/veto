from __future__ import annotations

from rest_framework import serializers

from apps.clients.models import ClientClinic

from .models import Reminder, ReminderPreference


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
            "provider",
            "provider_message_id",
            "provider_status",
            "recipient",
            "subject",
            "body",
            "scheduled_for",
            "sent_at",
            "delivered_at",
            "attempts",
            "max_attempts",
            "last_error",
            "last_webhook_payload",
            "created_at",
            "updated_at",
        ]

    def get_owner_name(self, obj):
        owner = getattr(getattr(obj, "patient", None), "owner", None)
        if not owner:
            return ""
        return f"{owner.first_name} {owner.last_name}".strip()


class ReminderPreferenceSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ReminderPreference
        fields = [
            "id",
            "clinic",
            "client",
            "client_name",
            "allow_email",
            "allow_sms",
            "preferred_channel",
            "timezone",
            "quiet_hours_start",
            "quiet_hours_end",
            "notes",
            "updated_at",
            "created_at",
        ]
        read_only_fields = ["clinic", "updated_at", "created_at"]

    def validate_client(self, value):
        request = self.context.get("request")
        clinic_id = getattr(getattr(request, "user", None), "clinic_id", None)
        if not clinic_id:
            return value
        if not ClientClinic.objects.filter(
            clinic_id=clinic_id,
            client_id=value.id,
            is_active=True,
        ).exists():
            raise serializers.ValidationError("Client must be an active member of your clinic.")
        return value

    def validate(self, attrs):
        start = attrs.get("quiet_hours_start")
        end = attrs.get("quiet_hours_end")
        instance = getattr(self, "instance", None)
        if instance:
            if start is None:
                start = instance.quiet_hours_start
            if end is None:
                end = instance.quiet_hours_end

        if (start is None) != (end is None):
            raise serializers.ValidationError(
                "Both quiet_hours_start and quiet_hours_end must be set together."
            )
        return attrs

    def get_client_name(self, obj):
        if not obj.client_id:
            return ""
        return f"{obj.client.first_name} {obj.client.last_name}".strip()
