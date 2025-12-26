from __future__ import annotations

from datetime import date as date_type

from django.core.exceptions import PermissionDenied
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.medical.models import ClinicalExam, Prescription
from apps.medical.serializers import (
    ClinicalExamReadSerializer,
    ClinicalExamWriteSerializer,
    PrescriptionReadSerializer,
    PrescriptionWriteSerializer,
)
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.scheduling.serializers import AppointmentReadSerializer, AppointmentWriteSerializer
from apps.scheduling.services.availability import compute_availability


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    CRUD for appointments within the user's clinic.
    Supports filtering by date, vet, patient, and status.

    Additional sub-resources:
      - /api/appointments/<id>/exam/           (GET/POST/PATCH)
      - /api/appointments/<id>/close_visit/    (POST)
      - /api/appointments/<id>/prescriptions/ (GET/POST)
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

        vet_id = self.request.query_params.get("vet")
        if vet_id:
            qs = qs.filter(vet_id=vet_id)

        patient_id = self.request.query_params.get("patient")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)

        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)

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
        POST  /api/appointments/<id>/exam/   -> create if none exists
        PATCH /api/appointments/<id>/exam/   -> partial update
        """
        user = request.user
        appointment = self.get_object()  # clinic-scoped by queryset

        # Only vets can write
        if request.method in ("POST", "PATCH") and not getattr(user, "is_vet", False):
            raise PermissionDenied("Only vets can create/update clinical exam.")

        # Lock editing when visit is closed
        if request.method in ("POST", "PATCH") and appointment.status == "completed":
            return Response({"detail": "Visit is closed."}, status=400)

        exam = ClinicalExam.objects.filter(
            clinic_id=user.clinic_id,
            appointment_id=appointment.id,
        ).first()

        if request.method == "GET":
            if not exam:
                return Response({"detail": "No clinical exam for this appointment."}, status=404)
            return Response(ClinicalExamReadSerializer(exam).data, status=200)

        if request.method == "POST":
            if exam:
                return Response({"detail": "Exam already exists."}, status=400)

            serializer = ClinicalExamWriteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            exam = serializer.save(
                clinic_id=user.clinic_id,
                appointment=appointment,
                created_by=user,
            )
            return Response(ClinicalExamReadSerializer(exam).data, status=201)

        # PATCH
        if not exam:
            return Response({"detail": "No clinical exam for this appointment."}, status=404)

        serializer = ClinicalExamWriteSerializer(exam, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        exam = serializer.save()
        return Response(ClinicalExamReadSerializer(exam).data, status=200)

    @action(detail=True, methods=["post"], url_path="close_visit")
    def close_visit(self, request, pk=None):
        """
        POST /api/appointments/<id>/close_visit/

        Rules:
          - Only vets can close a visit (403 otherwise)
          - ClinicalExam must exist (400 otherwise)
          - Appointment must be in the user's clinic (enforced by queryset)
          - Idempotent: if already completed -> 204
        """
        user = request.user
        appt = self.get_object()

        if not getattr(user, "is_vet", False):
            raise PermissionDenied("Only vets can close a visit.")

        has_exam = ClinicalExam.objects.filter(
            clinic_id=user.clinic_id,
            appointment_id=appt.id,
        ).exists()

        if not has_exam:
            return Response(
                {"detail": "Clinical exam is required before closing the visit."},
                status=400,
            )

        if appt.status == "completed":
            return Response(status=204)

        appt.status = "completed"
        appt.save(update_fields=["status"])
        return Response(status=204)

    @action(detail=True, methods=["get", "post"], url_path="prescriptions")
    def prescriptions(self, request, pk=None):
        """
        GET  /api/appointments/<id>/prescriptions/  -> list prescriptions
        POST /api/appointments/<id>/prescriptions/  -> create prescription

        Rules:
          - Create is vet-only
          - Create requires appointment.status == "completed"
          - Patient is derived from the appointment
        """
        user = request.user
        appt = self.get_object()

        if request.method == "GET":
            qs = Prescription.objects.filter(
                clinic_id=user.clinic_id,
                appointment_id=appt.id,
            ).order_by("-created_at")
            return Response(PrescriptionReadSerializer(qs, many=True).data, status=200)

        # POST
        if not getattr(user, "is_vet", False):
            raise PermissionDenied("Only vets can prescribe medication.")

        if appt.status != "completed":
            return Response(
                {"detail": "Visit must be closed before creating prescriptions."},
                status=400,
            )

        serializer = PrescriptionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rx = serializer.save(
            clinic_id=user.clinic_id,
            appointment_id=appt.id,
            patient_id=appt.patient_id,
            created_by=user,
        )
        return Response(PrescriptionReadSerializer(rx).data, status=201)


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
