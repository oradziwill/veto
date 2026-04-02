from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.reminders import services
from apps.reminders.models import Reminder, ReminderEvent, ReminderPreference


class Command(BaseCommand):
    help = "Process queued reminders and mark them as sent/failed with retry support."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--retry-minutes", type=int, default=15)

    def handle(self, *args, **options):
        now = timezone.now()
        limit = options["limit"]
        retry_minutes = options["retry_minutes"]

        reminders = list(
            Reminder.objects.filter(
                status__in=[Reminder.Status.QUEUED, Reminder.Status.DEFERRED],
                scheduled_for__lte=now,
            )
            .select_related("patient", "patient__owner", "clinic")
            .order_by("scheduled_for", "id")[:limit]
        )

        sent_count = 0
        failed_count = 0
        retry_count = 0
        deferred_count = 0
        cancelled_count = 0

        for reminder in reminders:
            preference = self._get_preference(reminder)
            if preference and not self._consent_allows_channel(reminder, preference):
                reminder.status = Reminder.Status.CANCELLED
                reminder.last_error = "Consent not granted for selected channel."
                reminder.save(update_fields=["status", "last_error", "updated_at"])
                ReminderEvent.objects.create(
                    reminder=reminder,
                    event_type=ReminderEvent.EventType.CANCELLED,
                    payload={"reason": "consent_denied"},
                )
                cancelled_count += 1
                continue

            should_defer, defer_until = services.should_defer_for_quiet_hours(
                reminder, preference, now=now
            )
            if should_defer and defer_until is not None:
                reminder.status = Reminder.Status.DEFERRED
                reminder.scheduled_for = defer_until
                reminder.last_error = "Deferred by quiet-hours policy."
                reminder.save(update_fields=["status", "scheduled_for", "last_error", "updated_at"])
                ReminderEvent.objects.create(
                    reminder=reminder,
                    event_type=ReminderEvent.EventType.DEFERRED,
                    payload={"defer_until": defer_until.isoformat()},
                )
                deferred_count += 1
                continue

            if (
                reminder.channel == Reminder.Channel.SMS
                and not reminder.clinic.reminder_sms_enabled
            ):
                reminder.status = Reminder.Status.CANCELLED
                reminder.last_error = "SMS reminders are disabled for this clinic."
                reminder.save(update_fields=["status", "last_error", "updated_at"])
                ReminderEvent.objects.create(
                    reminder=reminder,
                    event_type=ReminderEvent.EventType.CANCELLED,
                    payload={"reason": "reminder_sms_disabled"},
                )
                cancelled_count += 1
                continue

            reminder.attempts += 1
            try:
                provider_message_id, provider_status = services.send_reminder(reminder)
            except Exception as exc:  # noqa: BLE001 - command should continue processing queue
                reminder.last_error = str(exc)[:1000]
                if reminder.attempts >= reminder.max_attempts:
                    reminder.status = Reminder.Status.FAILED
                    ReminderEvent.objects.create(
                        reminder=reminder,
                        event_type=ReminderEvent.EventType.FAILED,
                        payload={"error": reminder.last_error},
                    )
                    failed_count += 1
                else:
                    reminder.status = Reminder.Status.QUEUED
                    reminder.scheduled_for = now + timedelta(minutes=retry_minutes)
                    retry_count += 1
                reminder.save(
                    update_fields=[
                        "attempts",
                        "status",
                        "scheduled_for",
                        "last_error",
                        "updated_at",
                    ]
                )
                continue

            reminder.status = Reminder.Status.SENT
            reminder.sent_at = now
            reminder.provider_message_id = provider_message_id
            reminder.provider_status = provider_status
            reminder.last_error = ""
            reminder.save(
                update_fields=[
                    "attempts",
                    "status",
                    "sent_at",
                    "provider",
                    "provider_message_id",
                    "provider_status",
                    "last_error",
                    "updated_at",
                ]
            )
            ReminderEvent.objects.create(
                reminder=reminder,
                event_type=ReminderEvent.EventType.SENT,
                payload={
                    "provider_message_id": provider_message_id,
                    "provider_status": provider_status,
                },
            )
            sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Processed reminders: "
                f"sent={sent_count}, failed={failed_count}, rescheduled={retry_count}, "
                f"deferred={deferred_count}, cancelled={cancelled_count}"
            )
        )

    @staticmethod
    def _get_preference(reminder: Reminder):
        owner_id = getattr(getattr(reminder, "patient", None), "owner_id", None)
        if not owner_id:
            return None
        return ReminderPreference.objects.filter(
            clinic_id=reminder.clinic_id,
            client_id=owner_id,
        ).first()

    @staticmethod
    def _consent_allows_channel(reminder: Reminder, preference: ReminderPreference) -> bool:
        if reminder.channel == Reminder.Channel.EMAIL:
            return preference.allow_email
        if reminder.channel == Reminder.Channel.SMS:
            return preference.allow_sms
        return False
