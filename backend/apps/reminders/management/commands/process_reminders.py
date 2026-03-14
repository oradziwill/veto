from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.reminders import services
from apps.reminders.models import Reminder


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
                status=Reminder.Status.QUEUED,
                scheduled_for__lte=now,
            ).order_by("scheduled_for", "id")[:limit]
        )

        sent_count = 0
        failed_count = 0
        retry_count = 0

        for reminder in reminders:
            reminder.attempts += 1
            try:
                services.send_reminder(reminder)
            except Exception as exc:  # noqa: BLE001 - command should continue processing queue
                reminder.last_error = str(exc)[:1000]
                if reminder.attempts >= reminder.max_attempts:
                    reminder.status = Reminder.Status.FAILED
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
            reminder.last_error = ""
            reminder.save(
                update_fields=["attempts", "status", "sent_at", "last_error", "updated_at"]
            )
            sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Processed reminders: "
                f"sent={sent_count}, failed={failed_count}, rescheduled={retry_count}"
            )
        )
