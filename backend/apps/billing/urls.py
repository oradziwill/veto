from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InvoiceViewSet, ServiceViewSet

router = DefaultRouter()
router.register(r"billing/services", ServiceViewSet, basename="billing-services")
router.register(r"billing/invoices", InvoiceViewSet, basename="billing-invoices")

urlpatterns = [
    path("", include(router.urls)),
]
