from __future__ import annotations

from datetime import date as date_type

from django.core.exceptions import PermissionDenied
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsDoctorOrAdmin, IsStaffOrVet
from apps.medical.models import ClinicalExam
from apps.medical.serializers import ClinicalExamReadSerializer, ClinicalExamWriteSerializer
from apps.patients.models import Patient
from apps.scheduling.models import Appointment, HospitalStay
from apps.scheduling.serializers import (
    AppointmentReadSerializer,
    AppointmentWriteSerializer,
    HospitalStayReadSerializer,
    HospitalStayWriteSerializer,
)
from apps.scheduling.services.availability import compute_availability


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    CRUD for appointments within the user's clinic.
    Supports filtering by date, vet, patient, and status.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user

        qs = (
            Appointment.objects.filter(clinic_id=user.clinic_id)
            .select_related("clinic", "patient", "vet")
            .order_by("starts_at")
        )

        # Optional filters
        day = self.request.query_params.get("date")
        if day:
            try:
                parsed = parse_date(day)
            except ValueError:
                parsed = None
            if parsed:
                qs = qs.filter(starts_at__date=parsed)

        date_from = self.request.query_params.get("date_from")
        if date_from:
            try:
                parsed_from = parse_date(date_from)
            except ValueError:
                parsed_from = None
            if parsed_from:
                qs = qs.filter(starts_at__date__gte=parsed_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            try:
                parsed_to = parse_date(date_to)
            except ValueError:
                parsed_to = None
            if parsed_to:
                qs = qs.filter(starts_at__date__lte=parsed_to)

        vet_id = self.request.query_params.get("vet")
        if vet_id:
            qs = qs.filter(vet_id=vet_id)

        patient_id = self.request.query_params.get("patient")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)

        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)

        visit_type = self.request.query_params.get("visit_type")
        if visit_type:
            qs = qs.filter(visit_type=visit_type)

        return qs

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return AppointmentReadSerializer
        return AppointmentWriteSerializer

    def perform_create(self, serializer):
        appointment = serializer.save(clinic=self.request.user.clinic)

        # Invalidate AI summary cache for the patient when a new visit is added
        if appointment.patient_id:
            patient = Patient.objects.get(pk=appointment.patient_id)
            patient.ai_summary = ""
            patient.ai_summary_updated_at = None
            patient.save(update_fields=["ai_summary", "ai_summary_updated_at"])

    def perform_update(self, serializer):
        serializer.save(clinic=self.request.user.clinic)

    @action(detail=True, methods=["get", "post", "patch"], url_path="exam")
    def exam(self, request, pk=None):
        """
        GET   /api/appointments/<id>/exam/   -> fetch exam (404 if none)
        POST  /api/appointments/<id>/exam/   -> create (400 if exists)
        PATCH /api/appointments/<id>/exam/   -> partial update
        """
        user = request.user
        appt = self.get_object()  # already clinic-scoped by queryset

        if request.method in ("POST", "PATCH") and not IsDoctorOrAdmin().has_permission(
            request, self
        ):
            raise PermissionDenied(
                "Only doctors and clinic admins can create/update clinical exam."
            )

        exam = (
            ClinicalExam.objects.filter(
                appointment_id=appt.id,
                clinic_id=user.clinic_id,
            )
            .order_by("id")
            .first()
        )

        if request.method == "GET":
            if not exam:
                return Response({"detail": "Not found."}, status=404)
            return Response(ClinicalExamReadSerializer(exam).data, status=200)

        if request.method == "POST":
            if exam:
                return Response({"detail": "Exam already exists."}, status=400)

            serializer = ClinicalExamWriteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            exam = serializer.save(
                clinic_id=user.clinic_id,
                appointment=appt,
                created_by=user,
            )
            return Response(ClinicalExamReadSerializer(exam).data, status=201)

        # PATCH
        if not exam:
            return Response({"detail": "Not found."}, status=404)

        serializer = ClinicalExamWriteSerializer(exam, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        exam = serializer.save()
        return Response(ClinicalExamReadSerializer(exam).data, status=200)

    @action(detail=True, methods=["post"], url_path="close-visit")
    def close_visit(self, request, pk=None):
        """
        POST /api/appointments/<id>/close-visit/
        Vet-only: marks the appointment as completed.
        """
        appt = self.get_object()  # clinic-scoped

        if not IsDoctorOrAdmin().has_permission(request, self):
            raise PermissionDenied("Only doctors and clinic admins can close a visit.")

        # If your domain wants a different terminal status, adjust here.
        appt.status = "completed"
        appt.save(update_fields=["status"])

        return Response(status=204)


class HospitalStayViewSet(viewsets.ModelViewSet):
    """
    CRUD for hospital stays (in-patient hospitalization).
    Doctor/Admin only for create/update.
    """

    permission_classes = [IsAuthenticated, HasClinic, IsDoctorOrAdmin]

    def get_queryset(self):
        user = self.request.user
        return (
            HospitalStay.objects.filter(clinic_id=user.clinic_id)
            .select_related("patient", "attending_vet", "admission_appointment")
            .order_by("-admitted_at")
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return HospitalStayReadSerializer
        return HospitalStayWriteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            HospitalStayReadSerializer(serializer.instance).data,
            status=201,
        )

    def perform_create(self, serializer):
        serializer.save(clinic_id=self.request.user.clinic_id, status="admitted")

    @action(detail=True, methods=["post"], url_path="discharge")
    def discharge(self, request, pk=None):
        """Discharge the patient from hospital."""
        from django.utils import timezone

        stay = self.get_object()
        if stay.status != "admitted":
            return Response(
                {"detail": "Stay is already discharged."},
                status=400,
            )
        stay.status = "discharged"
        stay.discharged_at = timezone.now()
        stay.discharge_notes = request.data.get("discharge_notes", "")
        stay.save(update_fields=["status", "discharged_at", "discharge_notes", "updated_at"])
        return Response(HospitalStayReadSerializer(stay).data)


class AvailabilityView(APIView):
    """
    Read-only endpoint returning available time slots for a given date.
    Optional vet-specific availability.
    """

    permission_classes = [IsAuthenticated, HasClinic]

    def get(self, request):
        user = request.user

        # ---- date validation (robust, no 500s) ----
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "Missing required query param: date=YYYY-MM-DD"},
                status=400,
            )

        try:
            parsed_day: date_type | None = parse_date(date_str)
        except ValueError:
            parsed_day = None

        if parsed_day is None:
            return Response(
                {"detail": "Invalid date. Use YYYY-MM-DD (e.g., 2025-12-23)."},
                status=400,
            )

        # ---- optional params ----
        vet = request.query_params.get("vet")
        vet_id = int(vet) if vet else None

        slot = request.query_params.get("slot")
        slot_minutes = int(slot) if slot else None

        # ---- compute availability ----
        data = compute_availability(
            clinic_id=user.clinic_id,
            date_str=date_str,
            vet_id=vet_id,
            slot_minutes=slot_minutes,
        )

        work_bounds = data.get("work_bounds")

        def dump_interval(interval):
            return {
                "start": interval.start.isoformat(),
                "end": interval.end.isoformat(),
            }

        return Response(
            {
                "date": date_str,
                "timezone": data["timezone"],
                "clinic_id": user.clinic_id,
                "vet_id": vet_id,
                "slot_minutes": data["slot_minutes"],
                "closed_reason": data.get("closed_reason"),
                "workday": dump_interval(work_bounds) if work_bounds else None,
                "work_intervals": [dump_interval(i) for i in data["work_intervals"]],
                "busy": [dump_interval(i) for i in data["busy_merged"]],
                "free": [dump_interval(i) for i in data["free_slots"]],
            }
        )
