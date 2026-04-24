from __future__ import annotations

import uuid

from django.db import models

from apps.tenancy.models import Clinic


class Device(models.Model):
    class DeviceType(models.TextChoices):
        LAB = "lab", "Lab"
        FISCAL = "fiscal", "Fiscal"

    class LifecycleState(models.TextChoices):
        DISCOVERED = "discovered", "Discovered"
        CONFIRMED = "confirmed", "Confirmed"
        ACTIVE = "active", "Active"
        OFFLINE = "offline", "Offline"

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="devices")
    device_type = models.CharField(max_length=16, choices=DeviceType.choices)
    lifecycle_state = models.CharField(
        max_length=16,
        choices=LifecycleState.choices,
        default=LifecycleState.DISCOVERED,
    )
    name = models.CharField(max_length=255)
    vendor = models.CharField(max_length=128, blank=True)
    model = models.CharField(max_length=128, blank=True)
    serial_number = models.CharField(max_length=128, blank=True)
    connection_type = models.CharField(max_length=32, blank=True)
    connection_config = models.JSONField(default=dict, blank=True)
    external_ref = models.CharField(
        max_length=128,
        blank=True,
        help_text="Agent-reported stable reference for upsert matching.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [
            models.Index(fields=["clinic", "device_type"]),
            models.Index(fields=["clinic", "lifecycle_state"]),
            models.Index(fields=["external_ref"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "external_ref"],
                condition=~models.Q(external_ref=""),
                name="device_management_device_clinic_external_ref_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.device_type})"


class DeviceCapability(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="capabilities")
    code = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["code", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["device", "code"],
                name="device_management_capability_device_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.device_id}:{self.code}"


class AgentNode(models.Model):
    class AgentStatus(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"
        DEGRADED = "degraded", "Degraded"

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="device_agents")
    node_id = models.CharField(max_length=128, db_index=True)
    name = models.CharField(max_length=128, blank=True)
    version = models.CharField(max_length=64, blank=True)
    host = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=16, choices=AgentStatus.choices, default=AgentStatus.ONLINE
    )
    metadata = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "node_id"],
                name="device_management_agent_clinic_node_uniq",
            )
        ]
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.node_id}@{self.clinic_id}"


class DeviceHeartbeat(models.Model):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="device_heartbeats")
    agent = models.ForeignKey(
        AgentNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="heartbeats",
    )
    payload = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [models.Index(fields=["clinic", "received_at"])]


class DeviceEvent(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="device_events")
    agent = models.ForeignKey(
        AgentNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.INFO)
    event_type = models.CharField(max_length=64)
    message = models.CharField(max_length=512, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["clinic", "severity", "created_at"])]


class DeviceCommand(models.Model):
    class CommandStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ACKED = "acked", "Acked"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="device_commands")
    agent = models.ForeignKey(
        AgentNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commands",
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commands",
    )
    command_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=CommandStatus.choices, default=CommandStatus.PENDING
    )
    result_payload = models.JSONField(default=dict, blank=True)
    error_message = models.CharField(max_length=512, blank=True)
    idempotency_key = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["clinic", "status", "created_at"])]


class FiscalReceipt(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT_TO_AGENT = "sent_to_agent", "Sent to agent"
        PRINTED = "printed", "Printed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        UNKNOWN = "unknown", "Unknown"

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="fiscal_receipts")
    device = models.ForeignKey(
        Device,
        on_delete=models.PROTECT,
        related_name="fiscal_receipts",
        limit_choices_to={"device_type": Device.DeviceType.FISCAL},
    )
    sale_ref = models.CharField(max_length=128, blank=True)
    buyer_tax_id = models.CharField(max_length=32, blank=True)
    gross_total = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default="PLN")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    payload = models.JSONField(default=dict, blank=True)
    idempotency_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    fiscal_number = models.CharField(max_length=128, blank=True)
    printed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["clinic", "status", "created_at"])]


class FiscalReceiptPrintAttempt(models.Model):
    receipt = models.ForeignKey(
        FiscalReceipt,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    command = models.ForeignKey(
        DeviceCommand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fiscal_attempts",
    )
    attempt_no = models.IntegerField(default=1)
    status = models.CharField(max_length=16, choices=DeviceCommand.CommandStatus.choices)
    message = models.CharField(max_length=512, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["receipt", "attempt_no"],
                name="device_management_fiscal_attempt_receipt_no_uniq",
            )
        ]
