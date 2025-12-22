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
        
        return qs.order_by("name")

    def perform_create(self, serializer):
        user = self.request.user
        if not getattr(user, "clinic_id", None):
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
