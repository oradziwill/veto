from apps.accounts.permissions import HasClinic, IsClinicAdmin
from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import WebhookSubscription
from .serializers import WebhookSubscriptionSerializer


class WebhookSubscriptionViewSet(viewsets.ModelViewSet):
    """
    CRUD integration webhooks (clinic admin only).

    list: GET /api/webhooks/subscriptions/
    create: POST /api/webhooks/subscriptions/
    """

    permission_classes = [IsAuthenticated, HasClinic, IsClinicAdmin]

    def get_queryset(self):
        return WebhookSubscription.objects.filter(
            clinic_id__in=accessible_clinic_ids(self.request.user)
        ).order_by("-created_at", "-id")

    def get_serializer_class(self):
        return WebhookSubscriptionSerializer

    def perform_create(self, serializer):
        cid = clinic_id_for_mutation(
            self.request.user, request=self.request, instance_clinic_id=None
        )
        serializer.save(
            clinic_id=cid,
            created_by=self.request.user,
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        clinic_id_for_mutation(
            self.request.user,
            request=self.request,
            instance_clinic_id=instance.clinic_id,
        )
        serializer.save()
