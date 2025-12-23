from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import HasClinic, IsVet

from .models import MedicalRecord
from .serializers import MedicalRecordReadSerializer, MedicalRecordWriteSerializer


class MedicalRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return MedicalRecordReadSerializer
        return MedicalRecordWriteSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            MedicalRecord.objects.select_related(
                "appointment",
                "created_by",
                "appointment__clinic",
            )
            .filter(appointment__clinic_id=user.clinic_id)
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        user = self.request.user

        if not IsVet().has_permission(self.request, self):
            raise PermissionDenied("Only vets can create medical records.")

        appointment = serializer.validated_data.get("appointment")

        if appointment.clinic_id != user.clinic_id:
            raise PermissionDenied("You cannot create medical records for another clinic.")

        if hasattr(appointment, "medical_record"):
            raise ValidationError("This appointment already has a medical record.")

        record = serializer.save(created_by=user)

        appointment.status = appointment.Status.COMPLETED
        appointment.save(update_fields=["status"])

        return record

    def perform_update(self, serializer):
        if not IsVet().has_permission(self.request, self):
            raise PermissionDenied("Only vets can update medical records.")
        serializer.save()
