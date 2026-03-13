from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin, IsStaffOrVet

from .models import MedicalRecord, PatientHistoryEntry, Prescription, Vaccination
from .serializers import (
    MedicalRecordReadSerializer,
    MedicalRecordWriteSerializer,
    PatientHistoryEntryReadSerializer,
    PatientHistoryEntryWriteSerializer,
    PrescriptionReadSerializer,
    VaccinationReadSerializer,
    VaccinationWriteSerializer,
)


class MedicalRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get_queryset(self):
        return MedicalRecord.objects.filter(clinic_id=self.request.user.clinic_id)

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return MedicalRecordReadSerializer
        return MedicalRecordWriteSerializer

    def perform_create(self, serializer):
        serializer.save(
            clinic_id=self.request.user.clinic_id,
            created_by=self.request.user,
        )


class PatientHistoryEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get_queryset(self):
        return PatientHistoryEntry.objects.filter(clinic_id=self.request.user.clinic_id)

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return PatientHistoryEntryReadSerializer
        return PatientHistoryEntryWriteSerializer

    def perform_create(self, serializer):
        serializer.save(
            clinic_id=self.request.user.clinic_id,
            created_by=self.request.user,
        )


class VaccinationViewSet(viewsets.ModelViewSet):
    """List, retrieve, update, destroy vaccinations. Create is via POST /api/patients/<id>/vaccinations/."""

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        return Vaccination.objects.filter(clinic_id=self.request.user.clinic_id).select_related(
            "patient", "clinic", "administered_by"
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return VaccinationReadSerializer
        return VaccinationWriteSerializer

    def create(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed

        raise MethodNotAllowed(
            "POST", detail="Create vaccinations via POST /api/patients/<id>/vaccinations/"
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        vaccination = serializer.save()
        vaccination = (
            Vaccination.objects.filter(pk=vaccination.pk)
            .select_related("patient", "clinic", "administered_by")
            .get()
        )
        return Response(VaccinationReadSerializer(vaccination).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class PrescriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve prescriptions. Create via POST /api/patients/<id>/prescriptions/."""

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        return Prescription.objects.filter(clinic_id=self.request.user.clinic_id).select_related(
            "patient", "clinic", "prescribed_by", "medical_record"
        )

    serializer_class = PrescriptionReadSerializer
