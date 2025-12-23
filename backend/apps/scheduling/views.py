from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsStaffOrVet

from .availability_serializers import AvailabilityResponseSerializer
from .models import Appointment
from .serializers import AppointmentReadSerializer, AppointmentWriteSerializer
from .services.availability import compute_availability


class AvailabilityView(APIView):
    permission_classes = [IsAuthenticated, HasClinic]

    def get(self, request):
        date = request.query_params.get("date")
        if not date:
            raise ValidationError({"date": "date is required (YYYY-MM-DD)"})

        vet = request.query_params.get("vet")
        vet_id = int(vet) if vet else None

        slot = request.query_params.get("slot_minutes")
        slot_minutes = int(slot) if slot else None

        data = compute_availability(
            clinic_id=request.user.clinic_id,
            date_str=date,
            vet_id=vet_id,
            slot_minutes=slot_minutes,
        )

        payload = {
            "date": date,
            "timezone": data["timezone"],
            "clinic_id": request.user.clinic_id,
            "vet_id": vet_id,
            "slot_minutes": data["slot_minutes"],
            "workday": {"start": data["work_bounds"].start, "end": data["work_bounds"].end},
            "work_intervals": [{"start": it.start, "end": it.end} for it in data["work_intervals"]],
            "busy": [
                {"appointment_id": appt_id, "start": interval.start, "end": interval.end}
                for appt_id, interval in data["busy_raw"]
            ],
            "free": [{"start": it.start, "end": it.end} for it in data["free_slots"]],
        }

        AvailabilityResponseSerializer(data=payload).is_valid(raise_exception=True)
        return Response(payload)


class AppointmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), HasClinic()]
        return [IsAuthenticated(), HasClinic(), IsStaffOrVet()]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return AppointmentReadSerializer
        return AppointmentWriteSerializer

    def get_queryset(self):
        user = self.request.user
        qs = (
            Appointment.objects.filter(clinic_id=user.clinic_id)
            .select_related("clinic", "patient", "vet")
            .order_by("starts_at")
        )

        date = self.request.query_params.get("date")
        if date:
            qs = qs.filter(starts_at__date=date)

        vet_id = self.request.query_params.get("vet")
        if vet_id:
            qs = qs.filter(vet_id=vet_id)

        patient_id = self.request.query_params.get("patient")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)

        return qs

    def perform_create(self, serializer):
        serializer.save(clinic=self.request.user.clinic)
