from __future__ import annotations

import hashlib
import hmac

from django.conf import settings
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasClinic, IsClinicAdmin, IsStaffOrVet

from .models import (
    Reminder,
    ReminderEvent,
    ReminderPreference,
    ReminderTemplate,
    ReminderTemplateVersion,
)
from .serializers import (
    ReminderPreferenceSerializer,
    ReminderReadSerializer,
    ReminderTemplatePreviewSerializer,
    ReminderTemplateSerializer,
)
from .services import render_message_template


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


class ReminderTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = ReminderTemplateSerializer

    def get_queryset(self):
        return (
            ReminderTemplate.objects.filter(clinic_id=self.request.user.clinic_id)
            .select_related("updated_by")
            .prefetch_related("versions", "versions__changed_by")
        )

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "preview"):
            permission_classes = [IsAuthenticated, HasClinic, IsClinicAdmin]
        else:
            permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        template = serializer.save(
            clinic_id=self.request.user.clinic_id,
            updated_by=self.request.user,
        )
        self._create_version_snapshot(template, self.request.user)

    def perform_update(self, serializer):
        template = serializer.save(
            clinic_id=self.request.user.clinic_id,
            updated_by=self.request.user,
        )
        self._create_version_snapshot(template, self.request.user)

    @action(
        detail=False,
        methods=["post"],
        url_path="preview",
        permission_classes=[IsAuthenticated, HasClinic, IsClinicAdmin],
    )
    def preview(self, request):
        payload = ReminderTemplatePreviewSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        template = None
        template_id = data.get("template_id")
        if template_id:
            template = ReminderTemplate.objects.filter(
                id=template_id,
                clinic_id=request.user.clinic_id,
            ).first()
            if not template:
                return Response({"detail": "Template not found."}, status=404)
        subject_template = data.get("subject_template", "")
        body_template = data.get("body_template", "")
        if template:
            subject_template = template.subject_template
            body_template = template.body_template
        context = data.get("context", {})
        subject = render_message_template(subject_template, context)
        body = render_message_template(body_template, context)
        return Response(
            {
                "subject": subject,
                "body": body,
                "context": context,
                "missing_keys_render_as_empty": True,
            },
            status=200,
        )

    @staticmethod
    def _create_version_snapshot(template: ReminderTemplate, changed_by):
        latest_version = (
            ReminderTemplateVersion.objects.filter(template=template).order_by("-version").first()
        )
        next_version = (latest_version.version if latest_version else 0) + 1
        ReminderTemplateVersion.objects.create(
            template=template,
            version=next_version,
            subject_template=template.subject_template,
            body_template=template.body_template,
            changed_by=changed_by,
        )


class ReminderWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, provider):
        if not self._authorize_webhook(request, provider):
            return Response({"detail": "Unauthorized webhook signature/token."}, status=401)

        updates = self._extract_updates(provider, request.data)
        if not updates:
            return Response({"detail": "No valid webhook updates in payload."}, status=400)

        updated = 0
        missing = 0
        for update in updates:
            reminder = Reminder.objects.filter(provider_message_id=update["message_id"]).first()
            if not reminder:
                missing += 1
                continue
            self._apply_update(reminder, update, provider, request.data)
            updated += 1

        if updated == 0:
            return Response({"detail": "Reminder not found for provided message ids."}, status=404)
        return Response({"ok": True, "updated": updated, "missing": missing}, status=200)

    def _authorize_webhook(self, request, provider: str) -> bool:
        raw_body = request.body or b""
        timestamp = request.headers.get("X-Webhook-Timestamp", "")
        signature = request.headers.get("X-Webhook-Signature", "")

        provider_secret_map = {
            "sendgrid": str(getattr(settings, "REMINDER_SENDGRID_WEBHOOK_SECRET", "")),
            "twilio": str(getattr(settings, "REMINDER_TWILIO_WEBHOOK_SECRET", "")),
        }
        secret = provider_secret_map.get(provider, "")
        if secret:
            if not (timestamp and signature):
                return False
            signed_payload = f"{timestamp}.{raw_body.decode('utf-8', errors='ignore')}"
            expected = hmac.new(
                secret.encode("utf-8"),
                signed_payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)

        # Backward-compatible fallback token.
        token = str(getattr(settings, "REMINDER_WEBHOOK_TOKEN", ""))
        if token:
            header_token = request.headers.get("X-Reminder-Webhook-Token", "")
            return hmac.compare_digest(token, header_token)
        return True

    def _extract_updates(self, provider: str, payload):
        if provider == "sendgrid":
            items = payload if isinstance(payload, list) else [payload]
            updates = []
            for item in items:
                message_id = (
                    item.get("message_id") or item.get("sg_message_id") or item.get("smtp-id") or ""
                )
                if message_id and ".filter" in message_id:
                    message_id = message_id.split(".filter")[0]
                status_value = item.get("status") or item.get("event") or ""
                updates.append(
                    {
                        "message_id": str(message_id),
                        "status": str(status_value),
                        "error": str(item.get("reason") or item.get("error") or ""),
                    }
                )
            return [u for u in updates if u["message_id"]]

        if provider == "twilio":
            message_id = payload.get("MessageSid") or payload.get("message_id") or ""
            status_value = payload.get("MessageStatus") or payload.get("status") or ""
            error_value = payload.get("ErrorMessage") or payload.get("ErrorCode") or ""
            if not message_id:
                return []
            return [
                {
                    "message_id": str(message_id),
                    "status": str(status_value),
                    "error": str(error_value),
                }
            ]

        # Generic payload support
        message_id = payload.get("message_id") or ""
        status_value = payload.get("status") or ""
        if not message_id:
            return []
        return [
            {
                "message_id": str(message_id),
                "status": str(status_value),
                "error": str(payload.get("error", "")),
            }
        ]

    def _apply_update(self, reminder: Reminder, update: dict, provider: str, payload):
        provider_status = update.get("status", "")
        status_map = {
            "accepted": Reminder.Status.SENT,
            "queued": Reminder.Status.SENT,
            "sent": Reminder.Status.SENT,
            "delivered": Reminder.Status.SENT,
            "processed": Reminder.Status.SENT,
            "failed": Reminder.Status.FAILED,
            "undelivered": Reminder.Status.FAILED,
            "bounced": Reminder.Status.FAILED,
            "rejected": Reminder.Status.FAILED,
            "dropped": Reminder.Status.FAILED,
        }
        mapped_status = status_map.get(str(provider_status).lower(), reminder.status)
        reminder.provider_status = str(provider_status)
        reminder.last_webhook_payload = payload
        reminder.status = mapped_status
        if str(provider_status).lower() == "delivered":
            reminder.delivered_at = timezone.now()
        if mapped_status == Reminder.Status.FAILED:
            reminder.last_error = str(update.get("error", ""))[:1000]
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
            payload={"provider": provider, "body": payload, "update": update},
        )
