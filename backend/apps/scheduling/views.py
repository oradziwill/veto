from django.utils.dateparse import parse_datetime
from rest_framework import decorators, permissions, response, viewsets

from .models import Appointment
from .serializers import AppointmentSerializer


class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # If you allow users with no clinic yet, return empty
        if not getattr(user, "clinic_id", None):
            return Appointment.objects.none()

        qs = (
            Appointment.objects.filter(clinic_id=user.clinic_id)
            .select_related("patient", "vet", "clinic")
            .order_by("starts_at")
        )

        dt_from = parse_datetime(self.request.query_params.get("from", "") or "")
        dt_to = parse_datetime(self.request.query_params.get("to", "") or "")

        # Return appointments overlapping the range
        if dt_from:
            qs = qs.filter(ends_at__gt=dt_from)
        if dt_to:
            qs = qs.filter(starts_at__lt=dt_to)

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            raise ValueError("User must belong to a clinic to create appointments.")
        serializer.save(clinic=user.clinic)

    @decorators.action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        qs = self.get_queryset().filter(vet=request.user)
        return response.Response(AppointmentSerializer(qs, many=True).data)
