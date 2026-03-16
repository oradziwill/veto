from __future__ import annotations

from django.conf import settings
from rest_framework import serializers

from apps.clients.models import ClientClinic

from .models import (
    Reminder,
    ReminderInboundReply,
    ReminderPreference,
    ReminderProviderConfig,
    ReminderTemplate,
    ReminderTemplateVersion,
)


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
            "experiment_key",
            "experiment_variant",
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
            "locale",
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


class ReminderTemplateVersionSerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source="changed_by.username", read_only=True)

    class Meta:
        model = ReminderTemplateVersion
        fields = [
            "id",
            "template",
            "version",
            "subject_template",
            "body_template",
            "changed_by",
            "changed_by_username",
            "created_at",
        ]
        read_only_fields = fields


class ReminderTemplateSerializer(serializers.ModelSerializer):
    versions = ReminderTemplateVersionSerializer(read_only=True, many=True)

    class Meta:
        model = ReminderTemplate
        fields = [
            "id",
            "clinic",
            "reminder_type",
            "channel",
            "locale",
            "is_active",
            "subject_template",
            "body_template",
            "updated_by",
            "created_at",
            "updated_at",
            "versions",
        ]
        read_only_fields = ["clinic", "updated_by", "created_at", "updated_at", "versions"]


class ReminderTemplatePreviewSerializer(serializers.Serializer):
    template_id = serializers.IntegerField(required=False)
    reminder_type = serializers.ChoiceField(choices=Reminder.ReminderType.choices)
    channel = serializers.ChoiceField(choices=Reminder.Channel.choices)
    locale = serializers.ChoiceField(choices=ReminderTemplate.Locale.choices, required=False)
    subject_template = serializers.CharField(required=False, allow_blank=True, default="")
    body_template = serializers.CharField(required=False, allow_blank=True, default="")
    context = serializers.DictField(required=False, default=dict)


class ReminderProviderConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderProviderConfig
        fields = [
            "id",
            "clinic",
            "email_provider",
            "sms_provider",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["clinic", "updated_by", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        email_provider = attrs.get(
            "email_provider",
            getattr(instance, "email_provider", ReminderProviderConfig.EmailProvider.INTERNAL),
        )
        sms_provider = attrs.get(
            "sms_provider",
            getattr(instance, "sms_provider", ReminderProviderConfig.SmsProvider.INTERNAL),
        )

        missing_requirements = []
        if email_provider == ReminderProviderConfig.EmailProvider.SENDGRID:
            if not self._setting("REMINDER_SENDGRID_API_KEY"):
                missing_requirements.append("REMINDER_SENDGRID_API_KEY")
            if not self._setting("REMINDER_SENDGRID_FROM_EMAIL"):
                missing_requirements.append("REMINDER_SENDGRID_FROM_EMAIL")
            if not self._setting("REMINDER_SENDGRID_WEBHOOK_SECRET"):
                missing_requirements.append("REMINDER_SENDGRID_WEBHOOK_SECRET")

        if sms_provider == ReminderProviderConfig.SmsProvider.TWILIO:
            if not self._setting("REMINDER_TWILIO_ACCOUNT_SID"):
                missing_requirements.append("REMINDER_TWILIO_ACCOUNT_SID")
            if not self._setting("REMINDER_TWILIO_AUTH_TOKEN"):
                missing_requirements.append("REMINDER_TWILIO_AUTH_TOKEN")
            if not self._setting("REMINDER_TWILIO_FROM_NUMBER"):
                missing_requirements.append("REMINDER_TWILIO_FROM_NUMBER")
            if not self._setting("REMINDER_TWILIO_WEBHOOK_SECRET"):
                missing_requirements.append("REMINDER_TWILIO_WEBHOOK_SECRET")

        if missing_requirements:
            raise serializers.ValidationError(
                {
                    "code": "provider_requirements_missing",
                    "missing_settings": sorted(set(missing_requirements)),
                    "detail": "Cannot enable external provider without required runtime settings.",
                }
            )
        return attrs

    @staticmethod
    def _setting(name: str) -> str:
        return str(getattr(settings, name, "")).strip()


class ReminderInboundReplySerializer(serializers.ModelSerializer):
    reminder_status = serializers.CharField(source="reminder.status", read_only=True)
    reminder_type = serializers.CharField(source="reminder.reminder_type", read_only=True)
    appointment_id = serializers.IntegerField(source="reminder.appointment_id", read_only=True)
    patient_name = serializers.CharField(source="reminder.patient.name", read_only=True)

    class Meta:
        model = ReminderInboundReply
        fields = [
            "id",
            "clinic",
            "reminder",
            "reminder_status",
            "reminder_type",
            "appointment_id",
            "patient_name",
            "provider",
            "provider_reply_id",
            "provider_message_id",
            "raw_text",
            "normalized_intent",
            "action_status",
            "action_note",
            "resolved_at",
            "payload",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
