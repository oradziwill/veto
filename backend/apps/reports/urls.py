from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import PortalBookingMetricsView, ReportExportJobViewSet

router = DefaultRouter()
router.register(r"reports/exports", ReportExportJobViewSet, basename="report-exports")

urlpatterns = [
    path("reports/portal-booking-metrics/", PortalBookingMetricsView.as_view()),
] + router.urls
