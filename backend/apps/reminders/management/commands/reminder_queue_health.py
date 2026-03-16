from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Min
from django.utils import timezone

from apps.reminders.models import Reminder

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Emit reminder queue health snapshot (counts + oldest queued age)."

    def handle(self, *args, **options):
        now = timezone.now()
        status_counts = dict(
            Reminder.objects.values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )
        oldest_queued = Reminder.objects.filter(status=Reminder.Status.QUEUED).aggregate(
            oldest=Min("scheduled_for")
        )["oldest"]
        oldest_age_seconds = (
            int((now - oldest_queued).total_seconds()) if oldest_queued is not None else 0
        )
        failed_last_24h = Reminder.objects.filter(
            status=Reminder.Status.FAILED,
            updated_at__gte=now - timedelta(hours=24),
        ).count()
        provider_counts = dict(
            Reminder.objects.values("provider")
            .annotate(total=Count("id"))
            .values_list("provider", "total")
        )

        payload = {
            "kind": "reminder_queue_health",
            "queued": status_counts.get(Reminder.Status.QUEUED, 0),
            "deferred": status_counts.get(Reminder.Status.DEFERRED, 0),
            "failed": status_counts.get(Reminder.Status.FAILED, 0),
            "sent": status_counts.get(Reminder.Status.SENT, 0),
            "cancelled": status_counts.get(Reminder.Status.CANCELLED, 0),
            "failed_last_24h": failed_last_24h,
            "provider_counts": provider_counts,
            "oldest_queued_age_seconds": oldest_age_seconds,
        }
        text = json.dumps(payload, sort_keys=True)
        self.stdout.write(text)
        logger.info(text)
