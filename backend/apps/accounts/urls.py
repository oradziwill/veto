from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ClinicUserViewSet, MeView, VetViewSet

router = DefaultRouter()
router.register(r"vets", VetViewSet, basename="vets")
router.register(r"users", ClinicUserViewSet, basename="users")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
]

urlpatterns += router.urls
