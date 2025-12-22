from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MeView, VetViewSet

router = DefaultRouter()
router.register(r"vets", VetViewSet, basename="vets")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
]

urlpatterns += router.urls
