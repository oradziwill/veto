from django.urls import path
from rest_framework.routers import DefaultRouter
<<<<<<< HEAD
from .views import MeView, VetsViewSet

router = DefaultRouter()
router.register(r"vets", VetsViewSet, basename="vets")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
] + router.urls
=======

from .views import MeView, VetViewSet

router = DefaultRouter()
router.register(r"vets", VetViewSet, basename="vets")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
]

urlpatterns += router.urls
>>>>>>> 6510c5a53af801136dfb834a4f1b5a7dc1afb1f4
