from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .integration_views import (
    LabDeviceIngestView,
    LabIngestionEnvelopeViewSet,
    LabIntegrationDeviceViewSet,
    LabObservationViewSet,
    LabSampleViewSet,
    LabTestCodeMapViewSet,
)
from .views import LabOrderViewSet, LabTestViewSet, LabViewSet

router = DefaultRouter()
router.register(r"labs", LabViewSet, basename="labs")
router.register(r"lab-tests", LabTestViewSet, basename="lab-tests")
router.register(r"lab-orders", LabOrderViewSet, basename="lab-orders")
router.register(
    r"lab-integration-devices", LabIntegrationDeviceViewSet, basename="lab-integration-devices"
)
router.register(r"lab-samples", LabSampleViewSet, basename="lab-samples")
router.register(r"lab-test-code-maps", LabTestCodeMapViewSet, basename="lab-test-code-maps")
router.register(
    r"lab-ingestion-envelopes", LabIngestionEnvelopeViewSet, basename="lab-ingestion-envelopes"
)
router.register(r"lab-observations", LabObservationViewSet, basename="lab-observations")

urlpatterns = [
    path(
        "lab-devices/<int:device_id>/ingest/",
        LabDeviceIngestView.as_view(),
        name="lab-device-ingest",
    ),
    path("", include(router.urls)),
]
