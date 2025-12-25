from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MedicalRecordViewSet, PatientHistoryEntryViewSet

router = DefaultRouter()
router.register(r"medical/records", MedicalRecordViewSet, basename="medical-records")
router.register(r"medical/history", PatientHistoryEntryViewSet, basename="medical-history")

urlpatterns = [
    path("", include(router.urls)),
]
