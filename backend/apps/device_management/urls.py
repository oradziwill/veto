from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AgentCommandPullView,
    AgentCommandResultView,
    AgentHeartbeatView,
    AgentRegisterView,
    DeviceCommandAdminViewSet,
    DeviceEventViewSet,
    DeviceInventoryUpsertView,
    DeviceViewSet,
    FiscalReceiptViewSet,
)

router = DefaultRouter()
router.register(r"device-management/devices", DeviceViewSet, basename="device-management-devices")
router.register(
    r"device-management/device-events", DeviceEventViewSet, basename="device-management-events"
)
router.register(r"fiscal/receipts", FiscalReceiptViewSet, basename="fiscal-receipts")
router.register(
    r"device-management/commands", DeviceCommandAdminViewSet, basename="device-management-commands"
)

urlpatterns = [
    path(
        "device-management/agents/register/",
        AgentRegisterView.as_view(),
        name="device-management-agent-register",
    ),
    path(
        "device-management/agents/heartbeat/",
        AgentHeartbeatView.as_view(),
        name="device-management-agent-heartbeat",
    ),
    path(
        "device-management/devices/upsert/",
        DeviceInventoryUpsertView.as_view(),
        name="device-management-devices-upsert",
    ),
    path(
        "device-management/agent/commands/",
        AgentCommandPullView.as_view(),
        name="device-management-agent-commands",
    ),
    path(
        "device-management/agent/commands/<int:command_id>/result/",
        AgentCommandResultView.as_view(),
        name="device-management-agent-command-result",
    ),
    path("", include(router.urls)),
]
