from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LabOrderViewSet, LabTestViewSet, LabViewSet

router = DefaultRouter()
router.register(r"labs", LabViewSet, basename="labs")
router.register(r"lab-tests", LabTestViewSet, basename="lab-tests")
router.register(r"lab-orders", LabOrderViewSet, basename="lab-orders")

urlpatterns = [
    path("", include(router.urls)),
]
