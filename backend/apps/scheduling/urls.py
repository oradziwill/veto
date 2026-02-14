from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AppointmentViewSet, AvailabilityView, HospitalStayViewSet

router = DefaultRouter()
router.register(r"appointments", AppointmentViewSet, basename="appointments")
router.register(r"hospital-stays", HospitalStayViewSet, basename="hospital-stays")

urlpatterns = [
    path("", include(router.urls)),
    path("availability/", AvailabilityView.as_view(), name="availability"),
]
