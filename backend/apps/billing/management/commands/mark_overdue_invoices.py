"""
Management command to mark sent invoices with due_date < today as overdue.
Usage: python manage.py mark_overdue_invoices
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.billing.models import Invoice

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Marks sent invoices with due_date before today as overdue."

    def handle(self, *args, **options):
        today = timezone.localdate()
        qs = Invoice.objects.filter(
            status=Invoice.Status.SENT,
            due_date__lt=today,
            due_date__isnull=False,
        )
        count = qs.update(status=Invoice.Status.OVERDUE)

        if count:
            self.stdout.write(self.style.SUCCESS(f"Marked {count} invoice(s) as overdue."))
        else:
            self.stdout.write("No invoices marked as overdue.")

        logger.info("mark_overdue_invoices marked %s invoice(s) as overdue", count)
