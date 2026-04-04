from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsClinicAdmin
from apps.audit.services import log_audit_event
from apps.audit.snapshots import client_membership_snapshot, client_snapshot
from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation

from .models import Client, ClientClinic
from .serializers import ClientClinicSerializer, ClientSerializer
from .services.gdpr_export import build_client_gdpr_export


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated, HasClinic]

    def get_queryset(self):
        ids = accessible_clinic_ids(self.request.user)
        if not ids:
            return Client.objects.none()

        qs = Client.objects.filter(memberships__clinic_id__in=ids, memberships__is_active=True)

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
                base_q |= Q(
                    first_name__icontains=parts[0], last_name__icontains=" ".join(parts[1:])
                )
                base_q |= Q(
                    first_name__icontains=" ".join(parts[1:]), last_name__icontains=parts[0]
                )
            qs = qs.filter(base_q)

        in_my_clinic = self.request.query_params.get("in_my_clinic")
        if in_my_clinic in ("0", "false", "False"):
            pass

        return qs.order_by("last_name", "first_name").distinct()

    def perform_create(self, serializer):
        cid = clinic_id_for_mutation(
            self.request.user, request=self.request, instance_clinic_id=None
        )
        client = serializer.save()
        ClientClinic.objects.get_or_create(
            client_id=client.id,
            clinic_id=cid,
            defaults={"is_active": True},
        )
        log_audit_event(
            clinic_id=cid,
            actor=self.request.user,
            action="client_created",
            entity_type="client",
            entity_id=client.id,
            after=client_snapshot(client),
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        cid = clinic_id_for_mutation(
            self.request.user,
            request=self.request,
            instance_clinic_id=None,
        )
        before = client_snapshot(instance)
        client = serializer.save()
        log_audit_event(
            clinic_id=cid,
            actor=self.request.user,
            action="client_updated",
            entity_type="client",
            entity_id=client.id,
            before=before,
            after=client_snapshot(client),
        )

    def perform_destroy(self, instance):
        cid = clinic_id_for_mutation(
            self.request.user, request=self.request, instance_clinic_id=None
        )
        entity_id = instance.id
        before = client_snapshot(instance)
        super().perform_destroy(instance)
        log_audit_event(
            clinic_id=cid,
            actor=self.request.user,
            action="client_deleted",
            entity_type="client",
            entity_id=entity_id,
            before=before,
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="gdpr-export",
        permission_classes=[permissions.IsAuthenticated, HasClinic, IsClinicAdmin],
    )
    def gdpr_export(self, request, pk=None):
        cid = clinic_id_for_mutation(request.user, request=request, instance_clinic_id=None)
        bundle = build_client_gdpr_export(client_id=int(pk), clinic_id=cid)
        if bundle is None:
            return Response({"detail": "Not found."}, status=404)
        log_audit_event(
            clinic_id=cid,
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
    """

    serializer_class = ClientClinicSerializer
    permission_classes = [permissions.IsAuthenticated, HasClinic]

    def get_queryset(self):
        ids = accessible_clinic_ids(self.request.user)
        if not ids:
            return ClientClinic.objects.none()
        return ClientClinic.objects.filter(clinic_id__in=ids).select_related("client", "clinic")

    def perform_create(self, serializer):
        cid = clinic_id_for_mutation(
            self.request.user, request=self.request, instance_clinic_id=None
        )
        membership = serializer.save(clinic_id=cid)
        log_audit_event(
            clinic_id=cid,
            actor=self.request.user,
            action="client_membership_created",
            entity_type="client_clinic",
            entity_id=membership.id,
            after=client_membership_snapshot(membership),
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        cid = clinic_id_for_mutation(
            self.request.user,
            request=self.request,
            instance_clinic_id=instance.clinic_id,
        )
        before = client_membership_snapshot(instance)
        membership = serializer.save(clinic_id=cid)
        log_audit_event(
            clinic_id=cid,
            actor=self.request.user,
            action="client_membership_updated",
            entity_type="client_clinic",
            entity_id=membership.id,
            before=before,
            after=client_membership_snapshot(membership),
        )

    def perform_destroy(self, instance):
        cid = instance.clinic_id
        entity_id = instance.id
        before = client_membership_snapshot(instance)
        super().perform_destroy(instance)
        log_audit_event(
            clinic_id=cid,
            actor=self.request.user,
            action="client_membership_deleted",
            entity_type="client_clinic",
            entity_id=entity_id,
            before=before,
        )
