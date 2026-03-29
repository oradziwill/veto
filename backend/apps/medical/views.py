from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin, IsStaffOrVet
from apps.audit.services import log_audit_event

from .models import (
    ClinicalExamTemplate,
    MedicalRecord,
    PatientHistoryEntry,
    Prescription,
    Vaccination,
)
from .serializers import (
    ClinicalExamTemplateReadSerializer,
    ClinicalExamTemplateWriteSerializer,
    MedicalRecordReadSerializer,
    MedicalRecordWriteSerializer,
    PatientHistoryEntryReadSerializer,
    PatientHistoryEntryWriteSerializer,
    PrescriptionReadSerializer,
    VaccinationReadSerializer,
    VaccinationWriteSerializer,
)


def _clinical_exam_template_audit_payload(template: ClinicalExamTemplate) -> dict:
    return {
        "name": template.name,
        "visit_type": template.visit_type,
        "is_active": template.is_active,
        "defaults": template.defaults or {},
    }


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


class ClinicalExamTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get_queryset(self):
        return ClinicalExamTemplate.objects.filter(clinic_id=self.request.user.clinic_id).order_by(
            "name", "id"
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ClinicalExamTemplateReadSerializer
        return ClinicalExamTemplateWriteSerializer

    def create(self, request, *args, **kwargs):
        clinic_id = self.request.user.clinic_id
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = serializer.save(
            clinic_id=clinic_id,
            created_by=self.request.user,
        )
        log_audit_event(
            clinic_id=clinic_id,
            actor=request.user,
            action="clinical_exam_template_created",
            entity_type="clinical_exam_template",
            entity_id=template.id,
            after=_clinical_exam_template_audit_payload(template),
        )
        return Response(ClinicalExamTemplateReadSerializer(template).data, status=201)

    def perform_update(self, serializer):
        instance = serializer.instance
        before = _clinical_exam_template_audit_payload(instance)
        template = serializer.save()
        log_audit_event(
            clinic_id=self.request.user.clinic_id,
            actor=self.request.user,
            action="clinical_exam_template_updated",
            entity_type="clinical_exam_template",
            entity_id=template.id,
            before=before,
            after=_clinical_exam_template_audit_payload(template),
        )
        return template

    def perform_destroy(self, instance):
        clinic_id = self.request.user.clinic_id
        entity_id = instance.id
        before = _clinical_exam_template_audit_payload(instance)
        super().perform_destroy(instance)
        log_audit_event(
            clinic_id=clinic_id,
            actor=self.request.user,
            action="clinical_exam_template_deleted",
            entity_type="clinical_exam_template",
            entity_id=entity_id,
            before=before,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(
            ClinicalExamTemplateReadSerializer(serializer.instance).data,
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class PatientHistoryEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get_queryset(self):
        return (
            PatientHistoryEntry.objects.filter(clinic_id=self.request.user.clinic_id)
            .select_related("record", "appointment", "invoice")
            .prefetch_related("invoice__lines")
        )

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

    def _parse_due_within_days(self):
        raw = self.request.query_params.get("due_within_days")
        if raw in (None, ""):
            return None
        try:
            days = int(raw)
        except (TypeError, ValueError) as err:
            raise ValidationError({"due_within_days": "Must be a positive integer."}) from err
        if days < 0:
            raise ValidationError({"due_within_days": "Must be a positive integer."})
        return days

    def get_queryset(self):
        qs = Vaccination.objects.filter(clinic_id=self.request.user.clinic_id).select_related(
            "patient", "clinic", "administered_by"
        )
        due_within_days = self._parse_due_within_days()
        if due_within_days is not None:
            today = timezone.localdate()
            due_before = today + timedelta(days=due_within_days)
            qs = qs.filter(
                next_due_at__isnull=False,
                next_due_at__lte=due_before,
            )
            if self.request.query_params.get("include_overdue") != "1":
                qs = qs.filter(next_due_at__gte=today)
        return qs

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
        qs = Prescription.objects.filter(clinic_id=self.request.user.clinic_id).select_related(
            "patient", "clinic", "prescribed_by", "medical_record"
        )
        patient_id = self.request.query_params.get("patient")
        medical_record_id = self.request.query_params.get("medical_record")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        if medical_record_id:
            qs = qs.filter(medical_record_id=medical_record_id)
        return qs

    serializer_class = PrescriptionReadSerializer
