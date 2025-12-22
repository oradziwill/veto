from rest_framework.routers import DefaultRouter
from .views import PatientViewSet

router = DefaultRouter()
router.register(r"patients", PatientViewSet, basename="patients")

urlpatterns = router.urls
<<<<<<< HEAD

=======
>>>>>>> 6510c5a53af801136dfb834a4f1b5a7dc1afb1f4
