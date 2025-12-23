from __future__ import annotations

from datetime import date as date_type

from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.scheduling.serializers import (
    AppointmentReadSerializer,
    AppointmentWriteSerializer,
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
