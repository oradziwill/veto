from rest_framework.routers import DefaultRouter
<<<<<<< HEAD
from .views import ClientViewSet

router = DefaultRouter()
router.register(r"clients", ClientViewSet, basename="clients")

urlpatterns = router.urls

=======
from .views import ClientViewSet, ClientClinicViewSet

router = DefaultRouter()
router.register(r"clients", ClientViewSet, basename="clients")
router.register(r"client-memberships", ClientClinicViewSet, basename="client-memberships")

urlpatterns = router.urls
>>>>>>> 6510c5a53af801136dfb834a4f1b5a7dc1afb1f4
