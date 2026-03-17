from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.billing.models import Invoice
from apps.inventory.models import InventoryItem
from apps.notifications.models import Notification
from apps.reminders.models import Reminder, ReminderEscalationRule
from apps.reminders.services import generate_portal_action_token
from apps.scheduling.models import Appointment


@pytest.mark.django_db
def test_notifications_list_read_read_all_and_unread_count(
    api_client, doctor, receptionist, clinic
):
    now = timezone.now()
    unread = Notification.objects.create(
        recipient=doctor,
        clinic=clinic,
        kind=Notification.Kind.LOW_STOCK,
        title="Low stock",
        body="Stock alert",
    )
    Notification.objects.create(
        recipient=doctor,
        clinic=clinic,
        kind=Notification.Kind.INVOICE_OVERDUE,
        title="Overdue",
        body="Invoice overdue",
        is_read=True,
        read_at=now - timedelta(days=2),
    )
    Notification.objects.create(
        recipient=doctor,
        clinic=clinic,
        kind=Notification.Kind.ESCALATION_TRIGGERED,
        title="Old read",
        body="Should not show",
        is_read=True,
        read_at=now - timedelta(days=10),
    )
    Notification.objects.create(
        recipient=receptionist,
        clinic=clinic,
        kind=Notification.Kind.LOW_STOCK,
        title="Other recipient",
        body="Should not show",
    )

    api_client.force_authenticate(user=doctor)
    listing = api_client.get("/api/notifications/")
    assert listing.status_code == 200
    assert "results" in listing.data
    ids = {row["id"] for row in listing.data["results"]}
    assert unread.id in ids
    assert len(ids) == 2

    count = api_client.get("/api/notifications/unread-count/")
    assert count.status_code == 200
    assert count.data["count"] == 1

    mark_one = api_client.post(f"/api/notifications/{unread.id}/read/")
    assert mark_one.status_code == 200
    unread.refresh_from_db()
    assert unread.is_read is True

    mark_all = api_client.post("/api/notifications/read-all/")
    assert mark_all.status_code == 200
    assert mark_all.data["ok"] is True
    count_after = api_client.get("/api/notifications/unread-count/")
    assert count_after.data["count"] == 0


@pytest.mark.django_db
def test_notification_created_on_portal_confirm(
    api_client, clinic, doctor, patient, client_with_membership
):
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=timezone.now() + timedelta(hours=4),
        ends_at=timezone.now() + timedelta(hours=5),
        status=Appointment.Status.SCHEDULED,
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        recipient=client_with_membership.email,
        scheduled_for=timezone.now(),
    )
    token = generate_portal_action_token(reminder, "confirm")

    response = api_client.post(f"/api/reminders/portal/{token}/", {}, format="json")
    assert response.status_code == 200
    assert Notification.objects.filter(
        clinic=clinic, kind=Notification.Kind.APPOINTMENT_CONFIRMED
    ).exists()


@pytest.mark.django_db
def test_notification_created_on_escalation_and_overdue_and_low_stock(
    api_client, clinic, doctor, patient, client_with_membership
):
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=timezone.now() + timedelta(hours=3),
        ends_at=timezone.now() + timedelta(hours=4),
        status=Appointment.Status.SCHEDULED,
    )
    Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        status=Reminder.Status.SENT,
        recipient=client_with_membership.email,
        subject="Please confirm",
        body="Reminder body",
        sent_at=timezone.now() - timedelta(hours=3),
        scheduled_for=timezone.now() - timedelta(hours=3),
    )
    ReminderEscalationRule.objects.create(
        clinic=clinic,
        name="Escalate unconfirmed",
        trigger_type=ReminderEscalationRule.TriggerType.APPOINTMENT_UNCONFIRMED,
        delay_minutes=60,
        action_type=ReminderEscalationRule.ActionType.ENQUEUE_FOLLOWUP,
        max_executions_per_target=1,
    )
    call_command("run_reminder_escalations")
    assert Notification.objects.filter(
        clinic=clinic,
        kind=Notification.Kind.ESCALATION_TRIGGERED,
    ).exists()

    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() - timedelta(days=1),
    )
    call_command("mark_overdue_invoices")
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.OVERDUE
    assert Notification.objects.filter(
        clinic=clinic,
        kind=Notification.Kind.INVOICE_OVERDUE,
    ).exists()

    item = InventoryItem.objects.create(
        clinic=clinic,
        name="Critical drug",
        sku="CRIT_DRUG",
        category=InventoryItem.Category.MEDICATION,
        unit="tabs",
        stock_on_hand=10,
        low_stock_threshold=5,
        created_by=doctor,
    )
    api_client.force_authenticate(user=doctor)
    movement = api_client.post(
        "/api/inventory/movements/",
        {"item": item.id, "kind": "out", "quantity": 6, "note": "dispensed"},
        format="json",
    )
    assert movement.status_code == 201
    assert Notification.objects.filter(
        clinic=clinic,
        kind=Notification.Kind.LOW_STOCK,
    ).exists()
