from rest_framework.routers import DefaultRouter

from .views import ReportExportJobViewSet

router = DefaultRouter()
router.register(r"reports/exports", ReportExportJobViewSet, basename="report-exports")

urlpatterns = router.urls
