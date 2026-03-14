from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReminderPreferenceViewSet, ReminderViewSet, ReminderWebhookView

router = DefaultRouter()
router.register(r"reminders", ReminderViewSet, basename="reminders")
router.register(r"reminder-preferences", ReminderPreferenceViewSet, basename="reminder-preferences")

urlpatterns = [
    path(
        "reminders/webhooks/<str:provider>/", ReminderWebhookView.as_view(), name="reminder-webhook"
    ),
    path("", include(router.urls)),
]
