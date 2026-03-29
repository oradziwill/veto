from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClinicalExamTemplateViewSet,
    MedicalRecordViewSet,
    PatientHistoryEntryViewSet,
    PrescriptionViewSet,
    VaccinationViewSet,
)

router = DefaultRouter()
router.register(
    r"medical/clinical-exam-templates",
    ClinicalExamTemplateViewSet,
    basename="clinical-exam-templates",
)
router.register(r"medical/records", MedicalRecordViewSet, basename="medical-records")
router.register(r"medical/history", PatientHistoryEntryViewSet, basename="medical-history")
router.register(r"prescriptions", PrescriptionViewSet, basename="prescriptions")
router.register(r"vaccinations", VaccinationViewSet, basename="vaccinations")

urlpatterns = [
    path("", include(router.urls)),
]
