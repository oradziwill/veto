from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin

from .models import MedicalRecord, PatientHistoryEntry
from .serializers import (
    MedicalRecordReadSerializer,
    MedicalRecordWriteSerializer,
    PatientHistoryEntryReadSerializer,
    PatientHistoryEntryWriteSerializer,
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
