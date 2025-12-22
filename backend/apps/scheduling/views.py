from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import HasClinic, IsStaffOrVet

from .models import Appointment
from .serializers import AppointmentReadSerializer, AppointmentWriteSerializer


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    permission_classes = [IsAuthenticated, HasClinic]

    def get_permissions(self):
        # Read is allowed for any clinic member
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), HasClinic()]

        # Write restricted for staff/vets
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
            .order_by("start_at")
        )

        # Optional filters for frontend:
        # /api/appointments/?date=2025-12-22
        date = self.request.query_params.get("date")
        if date:
            qs = qs.filter(start_at__date=date)

        vet_id = self.request.query_params.get("vet")
        if vet_id:
            qs = qs.filter(vet_id=vet_id)

        patient_id = self.request.query_params.get("patient")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)

        return qs

    def perform_create(self, serializer):
        # Force clinic to current user's clinic
        serializer.save(clinic=self.request.user.clinic)
