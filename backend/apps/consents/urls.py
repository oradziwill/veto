from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.consents.views import ConsentDocumentViewSet

router = DefaultRouter()
router.register(r"consent-documents", ConsentDocumentViewSet, basename="consent-documents")

app_name = "consents"

urlpatterns = [
    path("", include(router.urls)),
]
