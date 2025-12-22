from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import MedicalRecord
from .serializers import MedicalRecordReadSerializer, MedicalRecordWriteSerializer


class MedicalRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return MedicalRecordReadSerializer
        return MedicalRecordWriteSerializer

    def get_queryset(self):
        user = self.request.user

        if not getattr(user, "clinic_id", None):
            return MedicalRecord.objects.none()

        qs = MedicalRecord.objects.select_related(
            "appointment",
            "created_by",
            "appointment__clinic",
        ).filter(appointment__clinic_id=user.clinic_id)

        appt = self.request.query_params.get("appointment")
        if appt:
            qs = qs.filter(appointment_id=appt)

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        user = self.request.user
        if not getattr(user, "is_vet", False):
            raise PermissionDenied("Only vets can create medical records.")

        if not getattr(user, "clinic_id", None):
            raise ValidationError("User must belong to a clinic to create medical records.")

        appointment = serializer.validated_data.get("appointment")
        if appointment.clinic_id != user.clinic_id:
            raise PermissionDenied("You cannot create medical records for another clinic.")

        # One-to-one: prevent duplicates
        if hasattr(appointment, "medical_record"):
            raise ValidationError("This appointment already has a medical record.")

        record = serializer.save(created_by=user)

        # Auto-complete the appointment when the SOAP note is created
        # Use the exact enum value from Appointment.Status.COMPLETED
        appointment.status = appointment.Status.COMPLETED
        appointment.save(update_fields=["status"])

        return record

    def perform_update(self, serializer):
        user = self.request.user
        if not getattr(user, "is_vet", False):
            raise PermissionDenied("Only vets can update medical records.")
        serializer.save()
