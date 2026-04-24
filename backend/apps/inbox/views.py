from __future__ import annotations

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsStaffOrVet
from apps.inbox.models import InboxTask
from apps.inbox.serializers import InboxTaskSerializer
from apps.tenancy.access import accessible_clinic_ids, clinic_id_for_mutation


class InboxTaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = InboxTaskSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        clinic_ids = accessible_clinic_ids(user)
        qs = InboxTask.objects.filter(clinic_id__in=clinic_ids).select_related(
            "vet", "created_by", "closed_by"
        )
        role = getattr(user, "role", None)
        if role == "doctor":
            qs = qs.filter(vet=user)

        vet_id = self.request.query_params.get("vet")
        if vet_id:
            qs = qs.filter(vet_id=vet_id)

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.order_by("status", "-created_at")

    def perform_create(self, serializer):
        clinic_id = clinic_id_for_mutation(
            self.request.user, request=self.request, instance_clinic_id=None
        )
        serializer.save(clinic_id=clinic_id, created_by=self.request.user)

    @action(detail=True, methods=["patch"], url_path="set-status")
    def set_status(self, request, pk=None):
        task = self.get_object()
        new_status = request.data.get("status")
        if new_status not in (InboxTask.Status.OPEN, InboxTask.Status.IN_PROGRESS, InboxTask.Status.CLOSED):
            return Response({"detail": "Invalid status."}, status=400)

        task.status = new_status
        if new_status == InboxTask.Status.CLOSED:
            task.closed_by = request.user
            task.closed_at = timezone.now()
            task.close_comment = request.data.get("close_comment", "")
        elif new_status == InboxTask.Status.OPEN:
            task.closed_by = None
            task.closed_at = None
            task.close_comment = ""

        task.save()
        return Response(InboxTaskSerializer(task).data)
