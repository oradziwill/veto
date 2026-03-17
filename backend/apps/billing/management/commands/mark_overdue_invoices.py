"""
Management command to mark sent invoices with due_date < today as overdue.
Usage: python manage.py mark_overdue_invoices
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.billing.models import Invoice
from apps.notifications.models import Notification
from apps.notifications.services import notify_clinic_staff

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Marks sent invoices with due_date before today as overdue."

    def handle(self, *args, **options):
        today = timezone.localdate()
        qs = Invoice.objects.filter(
            status=Invoice.Status.SENT,
            due_date__lt=today,
            due_date__isnull=False,
        ).only("id", "clinic_id", "invoice_number", "due_date")
        invoices = list(qs)
        count = 0
        for invoice in invoices:
            invoice.status = Invoice.Status.OVERDUE
            invoice.save(update_fields=["status", "updated_at"])
            count += 1
            label = invoice.invoice_number or f"#{invoice.id}"
            notify_clinic_staff(
                clinic_id=invoice.clinic_id,
                kind=Notification.Kind.INVOICE_OVERDUE,
                title="Invoice became overdue",
                body=f"Invoice {label} is overdue since {invoice.due_date}.",
                link_tab="billing",
            )

        if count:
            self.stdout.write(self.style.SUCCESS(f"Marked {count} invoice(s) as overdue."))
        else:
            self.stdout.write("No invoices marked as overdue.")

        logger.info("mark_overdue_invoices marked %s invoice(s) as overdue", count)
