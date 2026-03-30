from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsClinicAdmin
from apps.audit.services import log_audit_event

from .models import Client, ClientClinic
from .serializers import ClientClinicSerializer, ClientSerializer
from .services.gdpr_export import build_client_gdpr_export


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

    @action(
        detail=True,
        methods=["get"],
        url_path="gdpr-export",
        permission_classes=[permissions.IsAuthenticated, HasClinic, IsClinicAdmin],
    )
    def gdpr_export(self, request, pk=None):
        clinic_id = getattr(request.user, "clinic_id", None)
        if not clinic_id:
            return Response({"detail": "Forbidden."}, status=403)
        bundle = build_client_gdpr_export(client_id=int(pk), clinic_id=clinic_id)
        if bundle is None:
            return Response({"detail": "Not found."}, status=404)
        log_audit_event(
            clinic_id=clinic_id,
            actor=request.user,
            action="client_gdpr_export_downloaded",
            entity_type="client",
            entity_id=pk,
            metadata={"format": "json"},
        )
        return Response(bundle)


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
