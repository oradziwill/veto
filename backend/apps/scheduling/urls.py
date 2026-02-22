from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppointmentViewSet,
    AvailabilityRoomsView,
    AvailabilityView,
    HospitalStayViewSet,
    RoomViewSet,
)

router = DefaultRouter()
router.register(r"appointments", AppointmentViewSet, basename="appointments")
router.register(r"hospital-stays", HospitalStayViewSet, basename="hospital-stays")
router.register(r"rooms", RoomViewSet, basename="rooms")

urlpatterns = [
    path("", include(router.urls)),
    path("availability/", AvailabilityView.as_view(), name="availability"),
    path("availability/rooms/", AvailabilityRoomsView.as_view(), name="availability-rooms"),
]
