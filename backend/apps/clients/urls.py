from rest_framework.routers import DefaultRouter

from .views import ClientClinicViewSet, ClientViewSet

router = DefaultRouter()
router.register(r"clients", ClientViewSet, basename="clients")
router.register(r"client-memberships", ClientClinicViewSet, basename="client-memberships")

urlpatterns = router.urls
