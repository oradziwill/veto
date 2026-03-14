from __future__ import annotations

from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.billing.models import Invoice
from apps.medical.models import Vaccination
from apps.reminders.models import Reminder, ReminderEvent, ReminderPreference
from apps.reminders.services import (
    build_reminder_context,
    pick_channel_and_recipient,
    render_reminder_content,
)
from apps.scheduling.models import Appointment


class Command(BaseCommand):
    help = (
        "Enqueue reminder records for upcoming appointments, vaccinations, and invoice due dates."
    )

    def add_arguments(self, parser):
        parser.add_argument("--appointment-hours", type=int, default=24)
        parser.add_argument("--vaccination-days", type=int, default=30)
        parser.add_argument("--invoice-days", type=int, default=7)

    def handle(self, *args, **options):
        now = timezone.now()

        appointment_count = self._enqueue_appointments(now, options["appointment_hours"])
        vaccination_count = self._enqueue_vaccinations(now, options["vaccination_days"])
        invoice_count = self._enqueue_invoices(now, options["invoice_days"])

        total = appointment_count + vaccination_count + invoice_count
        self.stdout.write(
            self.style.SUCCESS(
                f"Enqueued {total} reminder(s): appointments={appointment_count}, "
                f"vaccinations={vaccination_count}, invoices={invoice_count}"
            )
        )

    def _enqueue_appointments(self, now, hours_ahead: int) -> int:
        window_end = now + timedelta(hours=hours_ahead)
        qs = (
            Appointment.objects.filter(
                starts_at__gte=now,
                starts_at__lte=window_end,
                status__in=[Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED],
            )
            .select_related("patient", "patient__owner")
            .order_by("starts_at")
        )
        created = 0
        for appointment in qs:
            owner = appointment.patient.owner
            preference = self._get_preference(appointment.clinic_id, owner.id)
            channel, recipient = pick_channel_and_recipient(
                preference,
                email=owner.email,
                phone=owner.phone,
            )
            if not recipient:
                continue

            scheduled_for = max(appointment.starts_at - timedelta(hours=24), now)
            exists = Reminder.objects.filter(
                appointment_id=appointment.id,
                reminder_type=Reminder.ReminderType.APPOINTMENT,
                channel=channel,
            ).exclude(status=Reminder.Status.CANCELLED)
            if exists.exists():
                continue

            context = build_reminder_context(
                clinic_name=appointment.clinic.name,
                patient_name=appointment.patient.name,
                owner_name=f"{owner.first_name} {owner.last_name}".strip(),
                appointment_start=timezone.localtime(appointment.starts_at).isoformat(),
            )
            locale = getattr(preference, "locale", "en") if preference else "en"
            subject, body = render_reminder_content(
                clinic_id=appointment.clinic_id,
                reminder_type=Reminder.ReminderType.APPOINTMENT,
                channel=channel,
                locale=locale,
                context=context,
            )
            reminder = Reminder.objects.create(
                clinic_id=appointment.clinic_id,
                patient_id=appointment.patient_id,
                appointment_id=appointment.id,
                reminder_type=Reminder.ReminderType.APPOINTMENT,
                channel=channel,
                recipient=recipient,
                subject=subject,
                body=body,
                scheduled_for=scheduled_for,
            )
            ReminderEvent.objects.create(
                reminder=reminder, event_type=ReminderEvent.EventType.ENQUEUED
            )
            created += 1
        return created

    def _enqueue_vaccinations(self, now, days_ahead: int) -> int:
        today = timezone.localdate()
        due_end = today + timedelta(days=days_ahead)
        qs = (
            Vaccination.objects.filter(
                next_due_at__isnull=False, next_due_at__gte=today, next_due_at__lte=due_end
            )
            .select_related("patient", "patient__owner")
            .order_by("next_due_at")
        )
        created = 0
        for vaccination in qs:
            owner = vaccination.patient.owner
            preference = self._get_preference(vaccination.clinic_id, owner.id)
            channel, recipient = pick_channel_and_recipient(
                preference,
                email=owner.email,
                phone=owner.phone,
            )
            if not recipient:
                continue

            scheduled_for = max(
                timezone.make_aware(datetime.combine(today, time(hour=9, minute=0))),
                now,
            )
            exists = Reminder.objects.filter(
                vaccination_id=vaccination.id,
                reminder_type=Reminder.ReminderType.VACCINATION,
                channel=channel,
            ).exclude(status=Reminder.Status.CANCELLED)
            if exists.exists():
                continue

            context = build_reminder_context(
                clinic_name=vaccination.clinic.name,
                patient_name=vaccination.patient.name,
                owner_name=f"{owner.first_name} {owner.last_name}".strip(),
                due_date=vaccination.next_due_at.isoformat() if vaccination.next_due_at else "",
                vaccine_name=vaccination.vaccine_name,
            )
            locale = getattr(preference, "locale", "en") if preference else "en"
            subject, body = render_reminder_content(
                clinic_id=vaccination.clinic_id,
                reminder_type=Reminder.ReminderType.VACCINATION,
                channel=channel,
                locale=locale,
                context=context,
            )
            reminder = Reminder.objects.create(
                clinic_id=vaccination.clinic_id,
                patient_id=vaccination.patient_id,
                vaccination_id=vaccination.id,
                reminder_type=Reminder.ReminderType.VACCINATION,
                channel=channel,
                recipient=recipient,
                subject=subject,
                body=body,
                scheduled_for=scheduled_for,
            )
            ReminderEvent.objects.create(
                reminder=reminder, event_type=ReminderEvent.EventType.ENQUEUED
            )
            created += 1
        return created

    def _enqueue_invoices(self, now, days_ahead: int) -> int:
        today = timezone.localdate()
        due_end = today + timedelta(days=days_ahead)
        qs = (
            Invoice.objects.filter(
                due_date__isnull=False,
                due_date__gte=today,
                due_date__lte=due_end,
                status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE],
            )
            .select_related("client", "patient")
            .order_by("due_date")
        )
        created = 0
        for invoice in qs:
            preference = self._get_preference(invoice.clinic_id, invoice.client_id)
            channel, recipient = pick_channel_and_recipient(
                preference,
                email=invoice.client.email,
                phone=invoice.client.phone,
            )
            if not recipient:
                continue

            scheduled_for = now
            exists = Reminder.objects.filter(
                invoice_id=invoice.id,
                reminder_type=Reminder.ReminderType.INVOICE,
                channel=channel,
            ).exclude(status=Reminder.Status.CANCELLED)
            if exists.exists():
                continue

            patient_name = invoice.patient.name if invoice.patient_id else "your pet"
            context = build_reminder_context(
                clinic_name=invoice.clinic.name,
                patient_name=patient_name,
                owner_name=f"{invoice.client.first_name} {invoice.client.last_name}".strip(),
                due_date=invoice.due_date.isoformat() if invoice.due_date else "",
                invoice_number=str(invoice.id),
            )
            locale = getattr(preference, "locale", "en") if preference else "en"
            subject, body = render_reminder_content(
                clinic_id=invoice.clinic_id,
                reminder_type=Reminder.ReminderType.INVOICE,
                channel=channel,
                locale=locale,
                context=context,
            )
            reminder = Reminder.objects.create(
                clinic_id=invoice.clinic_id,
                patient_id=invoice.patient_id,
                invoice_id=invoice.id,
                reminder_type=Reminder.ReminderType.INVOICE,
                channel=channel,
                recipient=recipient,
                subject=subject,
                body=body,
                scheduled_for=scheduled_for,
            )
            ReminderEvent.objects.create(
                reminder=reminder, event_type=ReminderEvent.EventType.ENQUEUED
            )
            created += 1
        return created

    @staticmethod
    def _get_preference(clinic_id: int, client_id: int):
        return ReminderPreference.objects.filter(clinic_id=clinic_id, client_id=client_id).first()
