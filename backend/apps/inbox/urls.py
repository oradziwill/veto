from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.inbox.views import InboxTaskViewSet

router = DefaultRouter()
router.register(r"inbox", InboxTaskViewSet, basename="inbox")

urlpatterns = [
    path("", include(router.urls)),
]
