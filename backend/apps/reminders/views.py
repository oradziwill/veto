from __future__ import annotations

import hashlib
import hmac
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Count, Min, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from django.utils.dateparse import parse_date
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
    ReminderProviderConfig,
    ReminderTemplate,
    ReminderTemplateVersion,
)
from .serializers import (
    ReminderPreferenceSerializer,
    ReminderProviderConfigSerializer,
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

    @action(
        detail=False,
        methods=["get"],
        url_path="metrics",
        permission_classes=[IsAuthenticated, HasClinic, IsStaffOrVet],
    )
    def metrics(self, request):
        now = timezone.now()
        clinic_qs = Reminder.objects.filter(clinic_id=request.user.clinic_id)

        status_counts = dict(
            clinic_qs.values("status").annotate(total=Count("id")).values_list("status", "total")
        )
        provider_counts = dict(
            clinic_qs.values("provider")
            .annotate(total=Count("id"))
            .values_list("provider", "total")
        )
        oldest_queued = clinic_qs.filter(status=Reminder.Status.QUEUED).aggregate(
            oldest=Min("scheduled_for")
        )["oldest"]
        failed_last_24h = clinic_qs.filter(
            status=Reminder.Status.FAILED,
            updated_at__gte=now - timedelta(hours=24),
        ).count()

        payload = {
            "kind": "reminder_metrics_snapshot",
            "clinic_id": request.user.clinic_id,
            "status_counts": {
                "queued": status_counts.get(Reminder.Status.QUEUED, 0),
                "deferred": status_counts.get(Reminder.Status.DEFERRED, 0),
                "sent": status_counts.get(Reminder.Status.SENT, 0),
                "failed": status_counts.get(Reminder.Status.FAILED, 0),
                "cancelled": status_counts.get(Reminder.Status.CANCELLED, 0),
            },
            "provider_counts": provider_counts,
            "failed_last_24h": failed_last_24h,
            "oldest_queued_age_seconds": (
                int((now - oldest_queued).total_seconds()) if oldest_queued is not None else 0
            ),
            "generated_at": now.isoformat(),
        }
        return Response(payload, status=200)

    @action(
        detail=False,
        methods=["get"],
        url_path="analytics",
        permission_classes=[IsAuthenticated, HasClinic, IsClinicAdmin],
    )
    def analytics(self, request):
        period = request.query_params.get("period", "monthly")
        if period not in {"monthly", "daily"}:
            return Response(
                {"detail": "Invalid period. Use 'monthly' or 'daily'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()
        default_from = date(today.year, today.month, 1) - timedelta(days=150)
        from_date = parse_date(request.query_params.get("from", "")) or default_from
        to_date = parse_date(request.query_params.get("to", "")) or today
        if from_date > to_date:
            return Response(
                {"detail": "'from' must be earlier than or equal to 'to'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clinic_qs = Reminder.objects.filter(
            clinic_id=request.user.clinic_id,
            created_at__date__gte=from_date,
            created_at__date__lte=to_date,
        )
        channel = request.query_params.get("channel")
        provider = request.query_params.get("provider")
        reminder_type = request.query_params.get("type")
        if channel:
            clinic_qs = clinic_qs.filter(channel=channel)
        if provider:
            clinic_qs = clinic_qs.filter(provider=provider)
        if reminder_type:
            clinic_qs = clinic_qs.filter(reminder_type=reminder_type)

        total = clinic_qs.count()
        sent = clinic_qs.filter(status=Reminder.Status.SENT).count()
        failed = clinic_qs.filter(status=Reminder.Status.FAILED).count()
        cancelled = clinic_qs.filter(status=Reminder.Status.CANCELLED).count()
        delivered = clinic_qs.filter(delivered_at__isnull=False).count()

        trunc = TruncMonth("created_at") if period == "monthly" else TruncDate("created_at")
        grouped_rows = (
            clinic_qs.annotate(bucket=trunc)
            .values("bucket")
            .annotate(
                total=Count("id"),
                sent=Count("id", filter=Q(status=Reminder.Status.SENT)),
                delivered=Count("id", filter=Q(delivered_at__isnull=False)),
                failed=Count("id", filter=Q(status=Reminder.Status.FAILED)),
                cancelled=Count("id", filter=Q(status=Reminder.Status.CANCELLED)),
            )
            .order_by("bucket")
        )
        grouped_map = {
            row["bucket"].date() if hasattr(row["bucket"], "date") else row["bucket"]: row
            for row in grouped_rows
        }
        by_period = []
        for bucket_date in self._period_points(from_date, to_date, period):
            row = grouped_map.get(bucket_date, {})
            label = (
                f"{bucket_date.year:04d}-{bucket_date.month:02d}"
                if period == "monthly"
                else bucket_date.isoformat()
            )
            bucket_total = int(row.get("total", 0) or 0)
            bucket_sent = int(row.get("sent", 0) or 0)
            bucket_delivered = int(row.get("delivered", 0) or 0)
            bucket_failed = int(row.get("failed", 0) or 0)
            bucket_cancelled = int(row.get("cancelled", 0) or 0)
            by_period.append(
                {
                    "label": label,
                    "total": bucket_total,
                    "sent": bucket_sent,
                    "delivered": bucket_delivered,
                    "failed": bucket_failed,
                    "cancelled": bucket_cancelled,
                    "delivery_rate": round(
                        (bucket_delivered / bucket_total) if bucket_total else 0.0, 4
                    ),
                }
            )

        payload = {
            "kind": "reminder_analytics",
            "clinic_id": request.user.clinic_id,
            "period": period,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "filters": {
                "channel": channel or "",
                "provider": provider or "",
                "type": reminder_type or "",
            },
            "totals": {
                "total": total,
                "sent": sent,
                "delivered": delivered,
                "failed": failed,
                "cancelled": cancelled,
            },
            "rates": {
                "delivery_rate": round((delivered / total) if total else 0.0, 4),
                "failure_rate": round((failed / total) if total else 0.0, 4),
            },
            "by_period": by_period,
        }
        return Response(payload, status=200)

    @staticmethod
    def _period_points(from_date: date, to_date: date, period: str) -> list[date]:
        points = []
        if period == "monthly":
            cursor = date(from_date.year, from_date.month, 1)
            end = date(to_date.year, to_date.month, 1)
            while cursor <= end:
                points.append(cursor)
                if cursor.month == 12:
                    cursor = date(cursor.year + 1, 1, 1)
                else:
                    cursor = date(cursor.year, cursor.month + 1, 1)
            return points

        cursor = from_date
        while cursor <= to_date:
            points.append(cursor)
            cursor += timedelta(days=1)
        return points


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


class ReminderProviderConfigViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
    serializer_class = ReminderProviderConfigSerializer

    def get_queryset(self):
        return ReminderProviderConfig.objects.filter(clinic_id=self.request.user.clinic_id)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            permission_classes = [IsAuthenticated, HasClinic, IsClinicAdmin]
        else:
            permission_classes = [IsAuthenticated, HasClinic, IsStaffOrVet]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(clinic_id=self.request.user.clinic_id, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(clinic_id=self.request.user.clinic_id, updated_by=self.request.user)


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
