from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.documents.views import DocumentUploadView, IngestionDocumentViewSet

router = DefaultRouter()
router.register(r"documents", IngestionDocumentViewSet, basename="documents")

app_name = "documents"

urlpatterns = [
    path("documents/upload/", DocumentUploadView.as_view(), name="upload"),
    path("", include(router.urls)),
]
