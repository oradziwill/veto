from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import MeView, VetsViewSet

router = DefaultRouter()
router.register(r"vets", VetsViewSet, basename="vets")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
] + router.urls
