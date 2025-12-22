from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError

from .models import Client, ClientClinic
from .serializers import ClientClinicSerializer, ClientSerializer


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Client.objects.all()

        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(phone__icontains=q)
                | Q(email__icontains=q)
            )

        in_my_clinic = self.request.query_params.get("in_my_clinic")
        clinic_id = getattr(self.request.user, "clinic_id", None)

        if in_my_clinic in ("1", "true", "True"):
            if not clinic_id:
                return Client.objects.none()
            qs = qs.filter(memberships__clinic_id=clinic_id, memberships__is_active=True)

        return qs.order_by("last_name", "first_name").distinct()


class ClientClinicViewSet(viewsets.ModelViewSet):
    """
    Manage memberships (client <-> clinic links).
    We force clinic_id to the current user's clinic for safety.
    """

    serializer_class = ClientClinicSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        clinic_id = getattr(self.request.user, "clinic_id", None)
        if not clinic_id:
            return ClientClinic.objects.none()
        return ClientClinic.objects.filter(clinic_id=clinic_id).select_related("client", "clinic")

    def perform_create(self, serializer):
        clinic_id = getattr(self.request.user, "clinic_id", None)
        if not clinic_id:
            raise ValidationError("User must belong to a clinic to create memberships.")
        serializer.save(clinic_id=clinic_id)
