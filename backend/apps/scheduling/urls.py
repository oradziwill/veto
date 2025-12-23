from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AppointmentViewSet, AvailabilityView

router = DefaultRouter()
router.register(r"appointments", AppointmentViewSet, basename="appointments")

urlpatterns = [
    path("availability/", AvailabilityView.as_view(), name="availability"),
]

urlpatterns += router.urls
