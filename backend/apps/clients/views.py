from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError

from apps.accounts.permissions import HasClinic

from .models import Client, ClientClinic
from .serializers import ClientClinicSerializer, ClientSerializer


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated, HasClinic]

    def get_queryset(self):
        clinic_id = getattr(self.request.user, "clinic_id", None)
        if not clinic_id:
            return Client.objects.none()

        # Default to active memberships in current user's clinic.
        qs = Client.objects.filter(memberships__clinic_id=clinic_id, memberships__is_active=True)

        q = self.request.query_params.get("q")
        if q:
            parts = q.strip().split()
            base_q = (
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(phone__icontains=q)
                | Q(email__icontains=q)
            )
            if len(parts) >= 2:
                # Also match "Firstname Lastname" and "Lastname Firstname" as combined query
                base_q |= Q(
                    first_name__icontains=parts[0], last_name__icontains=" ".join(parts[1:])
                )
                base_q |= Q(
                    first_name__icontains=" ".join(parts[1:]), last_name__icontains=parts[0]
                )
            qs = qs.filter(base_q)

        # Keep compatibility with legacy query param; default is already clinic-scoped.
        in_my_clinic = self.request.query_params.get("in_my_clinic")
        if in_my_clinic in ("0", "false", "False"):
            # Do not broaden scope; endpoint remains clinic-scoped for safety.
            pass

        return qs.order_by("last_name", "first_name").distinct()

    def perform_create(self, serializer):
        clinic_id = getattr(self.request.user, "clinic_id", None)
        if not clinic_id:
            raise ValidationError("User must belong to a clinic to create clients.")
        client = serializer.save()
        ClientClinic.objects.get_or_create(
            client_id=client.id,
            clinic_id=clinic_id,
            defaults={"is_active": True},
        )


class ClientClinicViewSet(viewsets.ModelViewSet):
    """
    Manage memberships (client <-> clinic links).
    We force clinic_id to the current user's clinic for safety.
    """

    serializer_class = ClientClinicSerializer
    permission_classes = [permissions.IsAuthenticated, HasClinic]

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

    def perform_update(self, serializer):
        clinic_id = getattr(self.request.user, "clinic_id", None)
        if not clinic_id:
            raise ValidationError("User must belong to a clinic to update memberships.")
        # Prevent cross-clinic reassignment via PATCH/PUT.
        serializer.save(clinic_id=clinic_id)
