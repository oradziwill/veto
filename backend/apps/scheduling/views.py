from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.scheduling.services.availability import compute_availability

from .models import Appointment
from .serializers import AppointmentReadSerializer, AppointmentWriteSerializer


class AppointmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]

    def get_queryset(self):
        user = self.request.user
        return (
            Appointment.objects.filter(clinic_id=user.clinic_id)
            .select_related("clinic", "patient", "vet")
            .order_by("starts_at")
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return AppointmentReadSerializer
        return AppointmentWriteSerializer

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(clinic_id=user.clinic_id)


class AvailabilityView(APIView):
    permission_classes = [IsAuthenticated, HasClinic]

    def get(self, request):
        user = request.user

        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"detail": "Missing required query param: date=YYYY-MM-DD"}, status=400)

        vet = request.query_params.get("vet")
        vet_id = int(vet) if vet else None

        slot = request.query_params.get("slot")
        slot_minutes = int(slot) if slot else None

        data = compute_availability(
            clinic_id=user.clinic_id,
            date_str=date_str,
            vet_id=vet_id,
            slot_minutes=slot_minutes,
        )

        # IMPORTANT: work_bounds can be None (day off).
        work_bounds = data.get("work_bounds")

        def dump_interval(it):
            return {"start": it.start.isoformat(), "end": it.end.isoformat()}

        workday = None
        if work_bounds is not None:
            workday = dump_interval(work_bounds)

        return Response(
            {
                "date": date_str,
                "timezone": data["timezone"],
                "clinic_id": user.clinic_id,
                "vet_id": vet_id,
                "slot_minutes": data["slot_minutes"],
                "workday": workday,  # null on day off
                "work_intervals": [dump_interval(i) for i in data["work_intervals"]],
                "busy": [dump_interval(i) for i in data["busy_merged"]],
                "free": [dump_interval(i) for i in data["free_slots"]],
            }
        )
