from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ReminderInboundReplyViewSet,
    ReminderPortalActionView,
    ReminderPreferenceViewSet,
    ReminderProviderConfigViewSet,
    ReminderReplyWebhookView,
    ReminderTemplateViewSet,
    ReminderViewSet,
    ReminderWebhookView,
)

router = DefaultRouter()
router.register(r"reminders", ReminderViewSet, basename="reminders")
router.register(r"reminder-replies", ReminderInboundReplyViewSet, basename="reminder-replies")
router.register(r"reminder-preferences", ReminderPreferenceViewSet, basename="reminder-preferences")
router.register(
    r"reminder-provider-configs",
    ReminderProviderConfigViewSet,
    basename="reminder-provider-configs",
)
router.register(r"reminder-templates", ReminderTemplateViewSet, basename="reminder-templates")

urlpatterns = [
    path(
        "reminders/portal/<str:token>/",
        ReminderPortalActionView.as_view(),
        name="reminder-portal-action",
    ),
    path(
        "reminders/replies/<str:provider>/",
        ReminderReplyWebhookView.as_view(),
        name="reminder-reply-webhook",
    ),
    path(
        "reminders/webhooks/<str:provider>/", ReminderWebhookView.as_view(), name="reminder-webhook"
    ),
    path("", include(router.urls)),
]
