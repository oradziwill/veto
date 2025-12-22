<<<<<<< HEAD
from django.db import models
from rest_framework import viewsets, permissions
from .models import Client
from .serializers import ClientSerializer


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    # Temporarily allow unauthenticated access for development
    # Change back to [permissions.IsAuthenticated] for production
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        from apps.clients.models import ClientClinic
        
        # Search by name, phone, or email (use 'q' parameter as per API docs)
        search = self.request.query_params.get("q", "")
        qs = Client.objects.all()
        
        if search:
            qs = qs.filter(
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(phone__icontains=search) |
                models.Q(email__icontains=search)
            )
        
        # Filter by clinic membership if requested
        in_my_clinic = self.request.query_params.get("in_my_clinic", "")
        if in_my_clinic and hasattr(self.request.user, "clinic_id") and self.request.user.clinic_id:
            clinic_id = self.request.user.clinic_id
            client_ids = ClientClinic.objects.filter(
                clinic_id=clinic_id,
                is_active=True
            ).values_list("client_id", flat=True)
            qs = qs.filter(id__in=client_ids)
        
        return qs.order_by("last_name", "first_name")
=======
from rest_framework import viewsets, permissions
from rest_framework.exceptions import ValidationError
from django.db.models import Q

from .models import Client, ClientClinic
from .serializers import ClientSerializer, ClientClinicSerializer


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Client.objects.all()

        # Simple search: ?q=John
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(phone__icontains=q)
                | Q(email__icontains=q)
            )

        # Optional: restrict to clients linked to my clinic only:
        # /api/clients/?in_my_clinic=1
        in_my_clinic = self.request.query_params.get("in_my_clinic")
        user_clinic_id = getattr(self.request.user, "clinic_id", None)
        if in_my_clinic in ("1", "true", "True"):
            if not user_clinic_id:
                return Client.objects.none()
            qs = qs.filter(memberships__clinic_id=user_clinic_id, memberships__is_active=True)

        return qs.order_by("last_name", "first_name").distinct()


class ClientClinicViewSet(viewsets.ModelViewSet):
    """
    Manage memberships. Typically you won't expose this directly in the UI early,
    but it is useful for admin-like flows and future multi-clinic cases.
    """
    serializer_class = ClientClinicSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_clinic_id = getattr(self.request.user, "clinic_id", None)
        if not user_clinic_id:
            return ClientClinic.objects.none()
        return ClientClinic.objects.filter(clinic_id=user_clinic_id).select_related("client", "clinic")

    def perform_create(self, serializer):
        user_clinic_id = getattr(self.request.user, "clinic_id", None)
        if not user_clinic_id:
            raise ValidationError("User must belong to a clinic to create memberships.")
        # Force membership to the user's clinic for safety
        serializer.save(clinic_id=user_clinic_id)
>>>>>>> 6510c5a53af801136dfb834a4f1b5a7dc1afb1f4
