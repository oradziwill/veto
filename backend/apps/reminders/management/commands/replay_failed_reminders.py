from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.reminders.models import Reminder, ReminderEvent


class Command(BaseCommand):
    help = "Replay failed reminders by resetting them to queued."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument("--older-than-minutes", type=int, default=0)

    def handle(self, *args, **options):
        limit = options["limit"]
        older_than_minutes = options["older_than_minutes"]
        now = timezone.now()

        qs = Reminder.objects.filter(status=Reminder.Status.FAILED).order_by("updated_at", "id")
        if older_than_minutes > 0:
            cutoff = now - timedelta(minutes=older_than_minutes)
            qs = qs.filter(updated_at__lte=cutoff)
        reminders = list(qs[:limit])

        replayed = 0
        for reminder in reminders:
            reminder.status = Reminder.Status.QUEUED
            reminder.scheduled_for = now
            reminder.attempts = 0
            reminder.last_error = ""
            reminder.save(
                update_fields=[
                    "status",
                    "scheduled_for",
                    "attempts",
                    "last_error",
                    "updated_at",
                ]
            )
            ReminderEvent.objects.create(
                reminder=reminder,
                event_type=ReminderEvent.EventType.ENQUEUED,
                payload={"source": "replay_failed_reminders"},
            )
            replayed += 1

        self.stdout.write(self.style.SUCCESS(f"Replayed {replayed} failed reminder(s)."))
