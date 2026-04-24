from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation

from .models import (
    AgentNode,
    Device,
    DeviceCapability,
    DeviceCommand,
    DeviceEvent,
    DeviceHeartbeat,
    FiscalReceipt,
    FiscalReceiptPrintAttempt,
)


class DeviceCapabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceCapability
        fields = ["id", "code", "payload"]


class DeviceSerializer(serializers.ModelSerializer):
    capabilities = DeviceCapabilitySerializer(many=True, read_only=True)

    class Meta:
        model = Device
        fields = [
            "id",
            "clinic",
            "device_type",
            "lifecycle_state",
            "name",
            "vendor",
            "model",
            "serial_number",
            "connection_type",
            "connection_config",
            "external_ref",
            "is_active",
            "capabilities",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "capabilities"]


class AgentRegisterSerializer(serializers.Serializer):
    clinic_id = serializers.IntegerField(required=False)
    node_id = serializers.CharField(max_length=128)
    name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    version = serializers.CharField(max_length=64, required=False, allow_blank=True)
    host = serializers.CharField(max_length=128, required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)

    def create(self, validated_data):
        request = self.context["request"]
        cid = clinic_id_for_mutation(
            request.user,
            request=request,
            instance_clinic_id=validated_data.get("clinic_id"),
        )
        agent, _ = AgentNode.objects.update_or_create(
            clinic_id=cid,
            node_id=validated_data["node_id"],
            defaults={
                "name": validated_data.get("name", ""),
                "version": validated_data.get("version", ""),
                "host": validated_data.get("host", ""),
                "metadata": validated_data.get("metadata", {}),
                "status": AgentNode.AgentStatus.ONLINE,
                "last_seen_at": timezone.now(),
            },
        )
        return agent


class AgentHeartbeatSerializer(serializers.Serializer):
    clinic_id = serializers.IntegerField(required=False)
    node_id = serializers.CharField(max_length=128)
    status = serializers.ChoiceField(choices=AgentNode.AgentStatus.choices, required=False)
    payload = serializers.JSONField(required=False)
    version = serializers.CharField(max_length=64, required=False, allow_blank=True)
    host = serializers.CharField(max_length=128, required=False, allow_blank=True)

    def create(self, validated_data):
        request = self.context["request"]
        cid = clinic_id_for_mutation(
            request.user,
            request=request,
            instance_clinic_id=validated_data.get("clinic_id"),
        )
        agent, _ = AgentNode.objects.update_or_create(
            clinic_id=cid,
            node_id=validated_data["node_id"],
            defaults={
                "status": validated_data.get("status", AgentNode.AgentStatus.ONLINE),
                "version": validated_data.get("version", ""),
                "host": validated_data.get("host", ""),
                "last_seen_at": timezone.now(),
            },
        )
        heartbeat = DeviceHeartbeat.objects.create(
            clinic_id=cid,
            agent=agent,
            payload=validated_data.get("payload", {}),
        )
        return heartbeat


class DeviceUpsertItemSerializer(serializers.Serializer):
    external_ref = serializers.CharField(max_length=128)
    device_type = serializers.ChoiceField(choices=Device.DeviceType.choices)
    lifecycle_state = serializers.ChoiceField(
        choices=Device.LifecycleState.choices,
        required=False,
        default=Device.LifecycleState.DISCOVERED,
    )
    name = serializers.CharField(max_length=255)
    vendor = serializers.CharField(max_length=128, required=False, allow_blank=True)
    model = serializers.CharField(max_length=128, required=False, allow_blank=True)
    serial_number = serializers.CharField(max_length=128, required=False, allow_blank=True)
    connection_type = serializers.CharField(max_length=32, required=False, allow_blank=True)
    connection_config = serializers.JSONField(required=False)
    capabilities = serializers.ListField(child=serializers.CharField(max_length=64), required=False)
    is_active = serializers.BooleanField(required=False, default=True)


class DeviceInventoryUpsertSerializer(serializers.Serializer):
    clinic_id = serializers.IntegerField(required=False)
    node_id = serializers.CharField(max_length=128)
    devices = DeviceUpsertItemSerializer(many=True)

    def create(self, validated_data):
        request = self.context["request"]
        cid = clinic_id_for_mutation(
            request.user,
            request=request,
            instance_clinic_id=validated_data.get("clinic_id"),
        )
        agent = AgentNode.objects.filter(clinic_id=cid, node_id=validated_data["node_id"]).first()
        now = timezone.now()
        upserted = []
        for row in validated_data["devices"]:
            device, _ = Device.objects.update_or_create(
                clinic_id=cid,
                external_ref=row["external_ref"],
                defaults={
                    "device_type": row["device_type"],
                    "lifecycle_state": row["lifecycle_state"],
                    "name": row["name"],
                    "vendor": row.get("vendor", ""),
                    "model": row.get("model", ""),
                    "serial_number": row.get("serial_number", ""),
                    "connection_type": row.get("connection_type", ""),
                    "connection_config": row.get("connection_config", {}),
                    "is_active": row.get("is_active", True),
                },
            )
            caps = set(row.get("capabilities", []))
            if caps:
                existing = {c.code: c for c in device.capabilities.all()}
                for code in caps:
                    if code not in existing:
                        DeviceCapability.objects.create(device=device, code=code)
            upserted.append(device)
        if agent:
            agent.last_seen_at = now
            agent.status = AgentNode.AgentStatus.ONLINE
            agent.save(update_fields=["last_seen_at", "status", "updated_at"])
        return upserted


class DeviceCommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceCommand
        fields = [
            "id",
            "clinic",
            "agent",
            "device",
            "command_type",
            "payload",
            "status",
            "result_payload",
            "error_message",
            "idempotency_key",
            "created_at",
            "updated_at",
            "executed_at",
        ]
        read_only_fields = ["idempotency_key", "created_at", "updated_at", "executed_at"]


class DeviceCommandResultSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=DeviceCommand.CommandStatus.choices)
    result_payload = serializers.JSONField(required=False)
    error_message = serializers.CharField(max_length=512, required=False, allow_blank=True)


class DeviceEventWriteSerializer(serializers.ModelSerializer):
    clinic_id = serializers.IntegerField(required=False, write_only=True)

    class Meta:
        model = DeviceEvent
        fields = [
            "id",
            "clinic_id",
            "agent",
            "device",
            "severity",
            "event_type",
            "message",
            "payload",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]
        cid = clinic_id_for_mutation(
            request.user,
            request=request,
            instance_clinic_id=validated_data.pop("clinic_id", None),
        )
        validated_data["clinic_id"] = cid
        return super().create(validated_data)


class FiscalReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalReceipt
        fields = [
            "id",
            "clinic",
            "device",
            "sale_ref",
            "buyer_tax_id",
            "gross_total",
            "currency",
            "status",
            "payload",
            "idempotency_key",
            "fiscal_number",
            "printed_at",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "clinic",
            "status",
            "idempotency_key",
            "fiscal_number",
            "printed_at",
            "error_message",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        request = self.context["request"]
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        validated_data["clinic_id"] = cid
        return super().create(validated_data)


class FiscalReceiptPrintAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalReceiptPrintAttempt
        fields = [
            "id",
            "receipt",
            "command",
            "attempt_no",
            "status",
            "message",
            "payload",
            "created_at",
        ]
        read_only_fields = ["created_at"]


def queryset_for_user_devices(user):
    return Device.objects.filter(clinic_id__in=accessible_clinic_ids(user))
