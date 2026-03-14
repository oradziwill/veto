from __future__ import annotations

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasClinic, IsClinicAdmin, IsStaffOrVet

from .models import Reminder
from .serializers import ReminderReadSerializer


class ReminderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = ReminderReadSerializer

    def get_queryset(self):
        qs = Reminder.objects.filter(clinic_id=self.request.user.clinic_id).select_related(
            "patient", "patient__owner"
        )
        status_value = self.request.query_params.get("status")
        reminder_type = self.request.query_params.get("type")
        channel = self.request.query_params.get("channel")
        if status_value:
            qs = qs.filter(status=status_value)
        if reminder_type:
            qs = qs.filter(reminder_type=reminder_type)
        if channel:
            qs = qs.filter(channel=channel)
        return qs

    @action(
        detail=True,
        methods=["post"],
        url_path="resend",
        permission_classes=[IsAuthenticated, HasClinic, IsClinicAdmin],
    )
    def resend(self, request, pk=None):
        reminder = self.get_object()
        reminder.status = Reminder.Status.QUEUED
        reminder.scheduled_for = timezone.now()
        reminder.sent_at = None
        reminder.attempts = 0
        reminder.last_error = ""
        reminder.save(
            update_fields=[
                "status",
                "scheduled_for",
                "sent_at",
                "attempts",
                "last_error",
                "updated_at",
            ]
        )
        return Response(ReminderReadSerializer(reminder).data, status=status.HTTP_200_OK)
