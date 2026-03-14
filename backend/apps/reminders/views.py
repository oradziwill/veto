from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsClinicAdmin, IsStaffOrVet

from .models import Reminder, ReminderEvent, ReminderPreference
from .serializers import ReminderPreferenceSerializer, ReminderReadSerializer


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


class ReminderPreferenceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = ReminderPreferenceSerializer

    def get_queryset(self):
        return ReminderPreference.objects.filter(
            clinic_id=self.request.user.clinic_id
        ).select_related("client")

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            permission_classes = [IsAuthenticated, HasClinic, IsClinicAdmin]
        else:
            permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(clinic_id=self.request.user.clinic_id)

    def perform_update(self, serializer):
        serializer.save(clinic_id=self.request.user.clinic_id)


class ReminderWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, provider):
        token = str(getattr(settings, "REMINDER_WEBHOOK_TOKEN", ""))
        if token:
            header_token = request.headers.get("X-Reminder-Webhook-Token", "")
            if header_token != token:
                return Response({"detail": "Unauthorized webhook token."}, status=401)

        message_id = request.data.get("message_id")
        provider_status = request.data.get("status", "")
        if not message_id:
            return Response({"detail": "message_id is required."}, status=400)

        reminder = Reminder.objects.filter(provider_message_id=message_id).first()
        if not reminder:
            return Response({"detail": "Reminder not found for message_id."}, status=404)

        status_map = {
            "accepted": Reminder.Status.SENT,
            "sent": Reminder.Status.SENT,
            "delivered": Reminder.Status.SENT,
            "failed": Reminder.Status.FAILED,
            "bounced": Reminder.Status.FAILED,
            "rejected": Reminder.Status.FAILED,
        }
        mapped_status = status_map.get(str(provider_status).lower(), reminder.status)
        reminder.provider_status = str(provider_status)
        reminder.last_webhook_payload = request.data
        reminder.status = mapped_status
        if str(provider_status).lower() == "delivered":
            reminder.delivered_at = timezone.now()
        if mapped_status == Reminder.Status.FAILED:
            reminder.last_error = str(request.data.get("error", ""))[:1000]
        reminder.save(
            update_fields=[
                "provider_status",
                "last_webhook_payload",
                "status",
                "delivered_at",
                "last_error",
                "updated_at",
            ]
        )

        ReminderEvent.objects.create(
            reminder=reminder,
            event_type=ReminderEvent.EventType.WEBHOOK_UPDATE,
            payload={"provider": provider, "body": request.data},
        )
        return Response({"ok": True}, status=200)
