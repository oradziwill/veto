from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError

from apps.clients.models import ClientClinic
from apps.patients.models import Patient

from .serializers import PatientReadSerializer, PatientWriteSerializer


class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return PatientReadSerializer
        return PatientWriteSerializer

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            return Patient.objects.none()

        qs = (
            Patient.objects.filter(clinic_id=user.clinic_id)
            .select_related("owner", "primary_vet", "clinic")
            .order_by("name")
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

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            raise ValidationError("User must belong to a clinic to create patients.")

        patient = serializer.save(clinic=user.clinic)

        # Ensure client membership exists for this clinic
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
