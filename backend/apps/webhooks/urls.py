from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WebhookSubscriptionViewSet

router = DefaultRouter()
router.register(
    r"webhooks/subscriptions", WebhookSubscriptionViewSet, basename="webhook-subscriptions"
)

urlpatterns = [
    path("", include(router.urls)),
]
