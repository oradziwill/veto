from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import Invoice
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from apps.reminders.models import Reminder
from apps.tenancy.models import Clinic


@pytest.mark.django_db
def test_reminders_list_clinic_scoped(
    api_client, receptionist, clinic, patient, client_with_membership
):
    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=1),
    )
    own = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        invoice=invoice,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
        recipient="owner@example.com",
        scheduled_for=timezone.now(),
    )

    other_clinic = Clinic.objects.create(
        name="Clinic B",
        address="Street 2",
        phone="+48222222222",
        email="b@example.com",
    )
    other_owner = Client.objects.create(
        first_name="Other", last_name="Owner", email="other@example.com"
    )
    ClientClinic.objects.create(client=other_owner, clinic=other_clinic, is_active=True)
    other_doctor = User.objects.create_user(
        username="doctor_other_reminders",
        password="pass",
        clinic=other_clinic,
        role=User.Role.DOCTOR,
        is_vet=True,
    )
    other_patient = Patient.objects.create(
        clinic=other_clinic,
        owner=other_owner,
        name="OtherPet",
        species="Dog",
        primary_vet=other_doctor,
    )
    other_invoice = Invoice.objects.create(
        clinic=other_clinic,
        client=other_owner,
        patient=other_patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=1),
    )
    Reminder.objects.create(
        clinic=other_clinic,
        patient=other_patient,
        invoice=other_invoice,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
        recipient="other@example.com",
        scheduled_for=timezone.now(),
    )

    api_client.force_authenticate(user=receptionist)
    response = api_client.get("/api/reminders/")
    assert response.status_code == 200
    reminder_ids = {row["id"] for row in response.data}
    assert own.id in reminder_ids
    assert len(reminder_ids) == 1


@pytest.mark.django_db
def test_reminders_resend_admin_only(
    api_client, receptionist, clinic_admin, clinic, patient, client_with_membership
):
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
        scheduled_for=timezone.now() + timedelta(days=1),
        status=Reminder.Status.FAILED,
        attempts=3,
        last_error="provider down",
    )

    api_client.force_authenticate(user=receptionist)
    forbidden = api_client.post(f"/api/reminders/{reminder.id}/resend/")
    assert forbidden.status_code == 403

    api_client.force_authenticate(user=clinic_admin)
    ok = api_client.post(f"/api/reminders/{reminder.id}/resend/")
    assert ok.status_code == 200
    reminder.refresh_from_db()
    assert reminder.status == Reminder.Status.QUEUED
    assert reminder.attempts == 0
    assert reminder.last_error == ""
