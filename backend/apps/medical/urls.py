from rest_framework.routers import DefaultRouter
from .views import MedicalRecordViewSet

router = DefaultRouter()
router.register(r"medical-records", MedicalRecordViewSet, basename="medical-records")

urlpatterns = router.urls
