from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsVet
from apps.clients.models import ClientClinic
from apps.medical.models import PatientHistoryEntry
from apps.medical.serializers import (
    PatientHistoryEntryReadSerializer,
    PatientHistoryEntryWriteSerializer,
)
from apps.patients.models import Patient

from .serializers import PatientReadSerializer, PatientWriteSerializer


class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return PatientReadSerializer
        return PatientWriteSerializer

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            return Patient.objects.none()

        qs = Patient.objects.filter(clinic_id=user.clinic_id).select_related(
            "owner",
            "primary_vet",
            "clinic",
        )

        species = self.request.query_params.get("species")
        owner_id = self.request.query_params.get("owner")
        vet_id = self.request.query_params.get("vet")

        if species:
            qs = qs.filter(species__iexact=species)
        if owner_id:
            qs = qs.filter(owner_id=owner_id)
        if vet_id:
            qs = qs.filter(primary_vet_id=vet_id)

        return qs.order_by("name")

    def perform_create(self, serializer):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            raise ValidationError("User must belong to a clinic to create patients.")

        patient = serializer.save(clinic=user.clinic)

        # Ensure client membership exists (multi-clinic client model)
        if patient.owner_id and patient.clinic_id:
            ClientClinic.objects.get_or_create(
                client_id=patient.owner_id,
                clinic_id=patient.clinic_id,
                defaults={"is_active": True},
            )

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if (
            instance.clinic_id
            and getattr(user, "clinic_id", None) != instance.clinic_id
            and not user.is_superuser
        ):
            raise ValidationError("You cannot modify patients outside your clinic.")

        patient = serializer.save()

        if patient.owner_id and patient.clinic_id:
            ClientClinic.objects.get_or_create(
                client_id=patient.owner_id,
                clinic_id=patient.clinic_id,
                defaults={"is_active": True},
            )

    @action(detail=True, methods=["get", "post"], url_path="history")
    def history(self, request, pk=None):
        """
        GET  /api/patients/<id>/history/  -> list history entries for this patient (clinic scoped)
        POST /api/patients/<id>/history/  -> create new entry (vets only)
        """
        user = request.user
        patient = self.get_object()  # already clinic-filtered by get_queryset

        if request.method == "GET":
            qs = (
                PatientHistoryEntry.objects.filter(
                    clinic_id=user.clinic_id,
                    patient_id=patient.id,
                )
                .select_related("appointment", "created_by")
                .order_by("-created_at")
            )
            return Response(PatientHistoryEntryReadSerializer(qs, many=True).data)

        # POST requires vet
        if not IsVet().has_permission(request, self):
            raise PermissionDenied("Only vets can add history notes.")

        serializer = PatientHistoryEntryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment = serializer.validated_data.get("appointment")

        if appointment is not None:
            # Enforce tenant + patient match
            # (This prevents your earlier: "appointment from another clinic")
            if appointment.clinic_id != user.clinic_id:
                raise PermissionDenied("You cannot attach an appointment from another clinic.")
            if appointment.patient_id != patient.id:
                raise PermissionDenied("You cannot attach an appointment for a different patient.")

        entry = PatientHistoryEntry.objects.create(
            clinic_id=user.clinic_id,
            patient_id=patient.id,
            appointment=appointment,
            note=serializer.validated_data["note"],
            receipt_summary=serializer.validated_data.get("receipt_summary", ""),
            created_by=user,
        )

        return Response(PatientHistoryEntryReadSerializer(entry).data, status=201)
