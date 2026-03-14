from __future__ import annotations

import io
import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.billing.models import Invoice
from apps.reminders.models import Reminder


@pytest.mark.django_db
def test_replay_failed_reminders_resets_failed_items(clinic, patient, client_with_membership):
    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=1),
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        invoice=invoice,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
        recipient="owner@example.com",
        status=Reminder.Status.FAILED,
        attempts=3,
        last_error="timeout",
        scheduled_for=timezone.now() - timedelta(hours=1),
    )

    call_command("replay_failed_reminders", limit=10)

    reminder.refresh_from_db()
    assert reminder.status == Reminder.Status.QUEUED
    assert reminder.attempts == 0
    assert reminder.last_error == ""


@pytest.mark.django_db
def test_reminder_queue_health_prints_json_snapshot(clinic, patient, client_with_membership):
    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=1),
    )
    Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        invoice=invoice,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
        recipient="owner@example.com",
        status=Reminder.Status.QUEUED,
        scheduled_for=timezone.now() - timedelta(minutes=30),
    )

    out = io.StringIO()
    call_command("reminder_queue_health", stdout=out)
    payload = json.loads(out.getvalue().strip())

    assert payload["kind"] == "reminder_queue_health"
    assert payload["queued"] >= 1
    assert payload["oldest_queued_age_seconds"] >= 0
