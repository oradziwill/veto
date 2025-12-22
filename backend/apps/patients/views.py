<<<<<<< HEAD
from django.db import models
from rest_framework import viewsets, permissions
from .models import Patient
from .serializers import PatientSerializer


class PatientViewSet(viewsets.ModelViewSet):
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
            return Patient.objects.none()
        
        qs = Patient.objects.filter(clinic_id=user.clinic_id).select_related("owner", "primary_vet")
        
        # Filter by species
        species = self.request.query_params.get("species", "")
        if species:
            qs = qs.filter(species__icontains=species)
        
        # Filter by owner (client)
        owner = self.request.query_params.get("owner", "")
        if owner:
            try:
                owner_id = int(owner)
                qs = qs.filter(owner_id=owner_id)
            except ValueError:
                pass
        
        # Filter by vet
        vet = self.request.query_params.get("vet", "")
        if vet:
            try:
                vet_id = int(vet)
                qs = qs.filter(primary_vet_id=vet_id)
            except ValueError:
                pass
        
        # Search by name, species, or owner name (for backward compatibility)
        search = self.request.query_params.get("search", "")
        if search:
            qs = qs.filter(
                models.Q(name__icontains=search) |
                models.Q(species__icontains=search) |
                models.Q(owner__first_name__icontains=search) |
                models.Q(owner__last_name__icontains=search)
            )
        
=======
from rest_framework import viewsets, permissions
from rest_framework.exceptions import ValidationError

from apps.patients.models import Patient
from apps.clients.models import ClientClinic
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

        qs = Patient.objects.filter(clinic_id=user.clinic_id).select_related("owner", "primary_vet", "clinic")

        species = self.request.query_params.get("species")
        owner_id = self.request.query_params.get("owner")
        vet_id = self.request.query_params.get("vet")

        if species:
            qs = qs.filter(species__iexact=species)
        if owner_id:
            qs = qs.filter(owner_id=owner_id)
        if vet_id:
            qs = qs.filter(primary_vet_id=vet_id)

>>>>>>> 6510c5a53af801136dfb834a4f1b5a7dc1afb1f4
        return qs.order_by("name")

    def perform_create(self, serializer):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
<<<<<<< HEAD
            raise ValueError("User must belong to a clinic to create patients.")
        
        # Auto-create ClientClinic membership if needed
        from apps.clients.models import ClientClinic
        owner_id = serializer.validated_data.get('owner_id') or serializer.validated_data.get('owner')
        if owner_id:
            if isinstance(owner_id, int):
                ClientClinic.objects.get_or_create(
                    client_id=owner_id,
                    clinic_id=user.clinic_id,
                    defaults={'is_active': True}
                )
        
        serializer.save(clinic=user.clinic)
=======
            raise ValidationError("User must belong to a clinic to create patients.")

        patient = serializer.save(clinic=user.clinic)

        if patient.owner_id and patient.clinic_id:
            ClientClinic.objects.get_or_create(
                client_id=patient.owner_id,
                clinic_id=patient.clinic_id,
                defaults={"is_active": True},
            )

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if instance.clinic_id and getattr(user, "clinic_id", None) != instance.clinic_id and not user.is_superuser:
            raise ValidationError("You cannot modify patients outside your clinic.")

        patient = serializer.save()

        if patient.owner_id and patient.clinic_id:
            ClientClinic.objects.get_or_create(
                client_id=patient.owner_id,
                clinic_id=patient.clinic_id,
                defaults={"is_active": True},
            )
>>>>>>> 6510c5a53af801136dfb834a4f1b5a7dc1afb1f4
