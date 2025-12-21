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
