from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import Invoice
from apps.reminders.models import Reminder, ReminderPreference, ReminderTemplate
from apps.tenancy.models import Clinic


@pytest.mark.django_db
def test_reminder_templates_crud_and_version_history(
    api_client, clinic_admin, receptionist, clinic, client_with_membership
):
    api_client.force_authenticate(user=clinic_admin)
    create = api_client.post(
        "/api/reminder-templates/",
        {
            "reminder_type": Reminder.ReminderType.INVOICE,
            "channel": Reminder.Channel.EMAIL,
            "locale": "en",
            "subject_template": "Invoice reminder for {patient_name}",
            "body_template": "Invoice #{invoice_number} is due on {due_date}.",
        },
        format="json",
    )
    assert create.status_code == 201
    template_id = create.data["id"]

    template = ReminderTemplate.objects.get(id=template_id)
    assert template.versions.count() == 1
    assert template.versions.first().version == 1

    update = api_client.patch(
        f"/api/reminder-templates/{template_id}/",
        {"body_template": "Invoice #{invoice_number} due {due_date}."},
        format="json",
    )
    assert update.status_code == 200
    template.refresh_from_db()
    assert template.versions.count() == 2
    assert template.versions.first().version == 2

    api_client.force_authenticate(user=receptionist)
    list_response = api_client.get("/api/reminder-templates/")
    assert list_response.status_code == 200
    assert any(row["id"] == template_id for row in list_response.data)

    forbidden = api_client.post(
        "/api/reminder-templates/",
        {
            "reminder_type": Reminder.ReminderType.APPOINTMENT,
            "channel": Reminder.Channel.SMS,
            "locale": "pl",
            "body_template": "Wizyta dla {patient_name}.",
        },
        format="json",
    )
    assert forbidden.status_code == 403


@pytest.mark.django_db
def test_reminder_template_preview_missing_variables_and_clinic_scope(
    api_client, clinic_admin, clinic
):
    other_clinic = Clinic.objects.create(
        name="Clinic B",
        address="Street 2",
        phone="+48222222222",
        email="b@example.com",
    )
    other_admin = User.objects.create_user(
        username="other_template_admin",
        password="pass",
        clinic=other_clinic,
        role=User.Role.ADMIN,
        is_staff=True,
    )
    other_template = ReminderTemplate.objects.create(
        clinic=other_clinic,
        reminder_type=Reminder.ReminderType.VACCINATION,
        channel=Reminder.Channel.SMS,
        locale="pl",
        body_template="Szczepienie {patient_name} dnia {due_date}.",
        updated_by=other_admin,
    )
    api_client.force_authenticate(user=clinic_admin)
    response = api_client.post(
        "/api/reminder-templates/preview/",
        {
            "template_id": other_template.id,
            "reminder_type": Reminder.ReminderType.VACCINATION,
            "channel": Reminder.Channel.SMS,
            "locale": "pl",
            "context": {"patient_name": "Max"},
        },
        format="json",
    )
    assert response.status_code == 404

    inline = api_client.post(
        "/api/reminder-templates/preview/",
        {
            "reminder_type": Reminder.ReminderType.INVOICE,
            "channel": Reminder.Channel.EMAIL,
            "locale": "en",
            "subject_template": "Invoice for {patient_name}",
            "body_template": "Due {due_date}. Ref {missing_key}",
            "context": {"patient_name": "Max", "due_date": "2026-03-12"},
        },
        format="json",
    )
    assert inline.status_code == 200
    assert inline.data["subject"] == "Invoice for Max"
    assert inline.data["body"] == "Due 2026-03-12. Ref"


@pytest.mark.django_db
def test_enqueue_reminders_uses_locale_template(clinic, patient, client_with_membership):
    ReminderPreference.objects.create(
        clinic=clinic,
        client=client_with_membership,
        allow_email=True,
        allow_sms=False,
        preferred_channel=ReminderPreference.PreferredChannel.EMAIL,
        locale="pl",
    )
    ReminderTemplate.objects.create(
        clinic=clinic,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
        locale="pl",
        subject_template="Przypomnienie o fakturze dla {patient_name}",
        body_template="Faktura #{invoice_number} płatna do {due_date}.",
    )
    Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=2),
    )

    call_command("enqueue_reminders", appointment_hours=0, vaccination_days=0, invoice_days=7)

    reminder = Reminder.objects.get(
        clinic=clinic,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
    )
    assert reminder.subject.startswith("Przypomnienie o fakturze dla")
    assert "Faktura #" in reminder.body


@pytest.mark.django_db
def test_enqueue_reminders_fallback_template_when_locale_missing(
    clinic, patient, client_with_membership
):
    ReminderPreference.objects.create(
        clinic=clinic,
        client=client_with_membership,
        allow_email=True,
        allow_sms=False,
        preferred_channel=ReminderPreference.PreferredChannel.EMAIL,
        locale="pl",
    )
    Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=2),
    )

    call_command("enqueue_reminders", appointment_hours=0, vaccination_days=0, invoice_days=7)

    reminder = Reminder.objects.get(
        clinic=clinic,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
    )
    assert reminder.subject.startswith("Invoice reminder for")
    assert "Invoice #" in reminder.body
