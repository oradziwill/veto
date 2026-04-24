from django.contrib import admin

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


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "clinic",
        "device_type",
        "lifecycle_state",
        "vendor",
        "model",
        "is_active",
    )
    list_filter = ("device_type", "lifecycle_state", "is_active")
    search_fields = ("name", "vendor", "model", "serial_number", "external_ref")


@admin.register(DeviceCapability)
class DeviceCapabilityAdmin(admin.ModelAdmin):
    list_display = ("id", "device", "code")
    list_filter = ("code",)
    search_fields = ("device__name", "code")


@admin.register(AgentNode)
class AgentNodeAdmin(admin.ModelAdmin):
    list_display = ("id", "node_id", "clinic", "status", "version", "last_seen_at")
    list_filter = ("status",)
    search_fields = ("node_id", "name", "host")


@admin.register(DeviceHeartbeat)
class DeviceHeartbeatAdmin(admin.ModelAdmin):
    list_display = ("id", "clinic", "agent", "received_at")
    list_filter = ("clinic",)


@admin.register(DeviceEvent)
class DeviceEventAdmin(admin.ModelAdmin):
    list_display = ("id", "clinic", "severity", "event_type", "device", "created_at")
    list_filter = ("severity", "event_type")
    search_fields = ("event_type", "message")


@admin.register(DeviceCommand)
class DeviceCommandAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "clinic",
        "command_type",
        "status",
        "device",
        "agent",
        "created_at",
        "executed_at",
    )
    list_filter = ("status", "command_type")
    search_fields = ("command_type", "error_message")


@admin.register(FiscalReceipt)
class FiscalReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "clinic", "device", "status", "gross_total", "currency", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("sale_ref", "buyer_tax_id", "fiscal_number")


@admin.register(FiscalReceiptPrintAttempt)
class FiscalReceiptPrintAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "receipt", "attempt_no", "status", "created_at")
    list_filter = ("status",)
