from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReminderViewSet

router = DefaultRouter()
router.register(r"reminders", ReminderViewSet, basename="reminders")

urlpatterns = [
    path("", include(router.urls)),
]
