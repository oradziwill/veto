from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FiscalAgentStatusView, InvoiceViewSet, RevenueSummaryView, ServiceViewSet

router = DefaultRouter()
router.register(r"services", ServiceViewSet, basename="billing-services")
router.register(r"invoices", InvoiceViewSet, basename="billing-invoices")

urlpatterns = [
    path("revenue-summary/", RevenueSummaryView.as_view(), name="revenue-summary"),
    path("fiscal/agent-status/", FiscalAgentStatusView.as_view(), name="fiscal-agent-status"),
    path("", include(router.urls)),
]
