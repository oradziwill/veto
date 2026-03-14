from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import Invoice
from apps.clients.models import Client, ClientClinic
from apps.medical.models import Vaccination
from apps.patients.models import Patient
from apps.reminders.models import Reminder, ReminderPreference
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic


@pytest.mark.django_db
def test_enqueue_reminders_creates_records_for_core_workflows(
    clinic, patient, doctor, client_with_membership
):
    now = timezone.now()
    Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now + timedelta(hours=2),
        ends_at=now + timedelta(hours=2, minutes=30),
        status=Appointment.Status.SCHEDULED,
    )
    Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Rabies",
        administered_at=timezone.localdate() - timedelta(days=300),
        next_due_at=timezone.localdate() + timedelta(days=5),
        administered_by=doctor,
    )
    Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=2),
    )

    call_command("enqueue_reminders", appointment_hours=24, vaccination_days=30, invoice_days=7)

    assert Reminder.objects.filter(clinic=clinic).count() == 3
    assert Reminder.objects.filter(reminder_type=Reminder.ReminderType.APPOINTMENT).exists()
    assert Reminder.objects.filter(reminder_type=Reminder.ReminderType.VACCINATION).exists()
    assert Reminder.objects.filter(reminder_type=Reminder.ReminderType.INVOICE).exists()


@pytest.mark.django_db
def test_enqueue_reminders_idempotent_and_multi_clinic():
    clinic_a = Clinic.objects.create(
        name="Clinic A",
        address="Street 1",
        phone="+48111111111",
        email="a@example.com",
    )
    clinic_b = Clinic.objects.create(
        name="Clinic B",
        address="Street 2",
        phone="+48222222222",
        email="b@example.com",
    )
    owner_a = Client.objects.create(
        first_name="Alice", last_name="Owner", email="alice@example.com"
    )
    owner_b = Client.objects.create(first_name="Bob", last_name="Owner", email="bob@example.com")
    ClientClinic.objects.create(client=owner_a, clinic=clinic_a, is_active=True)
    ClientClinic.objects.create(client=owner_b, clinic=clinic_b, is_active=True)
    doctor_a = User.objects.create_user(
        username="doctor_a",
        password="pass",
        clinic=clinic_a,
        role=User.Role.DOCTOR,
        is_vet=True,
    )
    doctor_b = User.objects.create_user(
        username="doctor_b",
        password="pass",
        clinic=clinic_b,
        role=User.Role.DOCTOR,
        is_vet=True,
    )
    patient_a = Patient.objects.create(
        clinic=clinic_a,
        owner=owner_a,
        name="Max",
        species="Dog",
        primary_vet=doctor_a,
    )
    patient_b = Patient.objects.create(
        clinic=clinic_b,
        owner=owner_b,
        name="Luna",
        species="Cat",
        primary_vet=doctor_b,
    )

    now = timezone.now()
    Appointment.objects.create(
        clinic=clinic_a,
        patient=patient_a,
        vet=doctor_a,
        starts_at=now + timedelta(hours=2),
        ends_at=now + timedelta(hours=3),
        status=Appointment.Status.SCHEDULED,
    )
    Appointment.objects.create(
        clinic=clinic_b,
        patient=patient_b,
        vet=doctor_b,
        starts_at=now + timedelta(hours=2),
        ends_at=now + timedelta(hours=3),
        status=Appointment.Status.SCHEDULED,
    )

    call_command("enqueue_reminders")
    call_command("enqueue_reminders")

    assert Reminder.objects.filter(clinic=clinic_a).count() == 1
    assert Reminder.objects.filter(clinic=clinic_b).count() == 1


@pytest.mark.django_db
def test_process_reminders_marks_sent(clinic, patient, client_with_membership):
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
        subject="Invoice reminder",
        body="Please pay",
        scheduled_for=timezone.now() - timedelta(minutes=1),
    )

    call_command("process_reminders")

    reminder.refresh_from_db()
    assert reminder.status == Reminder.Status.SENT
    assert reminder.sent_at is not None
    assert reminder.attempts == 1


@pytest.mark.django_db
def test_process_reminders_retries_and_fails(clinic, patient, client_with_membership, monkeypatch):
    from apps.reminders import services

    source_invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=1),
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        invoice=source_invoice,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
        recipient="owner@example.com",
        subject="Invoice reminder",
        body="Please pay",
        scheduled_for=timezone.now() - timedelta(minutes=1),
        max_attempts=2,
    )

    def _always_fail(_reminder):
        raise RuntimeError("provider down")

    monkeypatch.setattr(services, "send_reminder", _always_fail)

    call_command("process_reminders", retry_minutes=1)
    reminder.refresh_from_db()
    assert reminder.status == Reminder.Status.QUEUED
    assert reminder.attempts == 1
    assert "provider down" in reminder.last_error

    reminder.scheduled_for = timezone.now() - timedelta(minutes=1)
    reminder.save(update_fields=["scheduled_for"])
    call_command("process_reminders", retry_minutes=1)
    reminder.refresh_from_db()
    assert reminder.status == Reminder.Status.FAILED
    assert reminder.attempts == 2


@pytest.mark.django_db
def test_process_reminders_cancels_when_no_consent(clinic, patient, client_with_membership):
    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=1),
    )
    ReminderPreference.objects.create(
        clinic=clinic,
        client=client_with_membership,
        allow_email=False,
        allow_sms=False,
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        invoice=invoice,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
        recipient="owner@example.com",
        scheduled_for=timezone.now() - timedelta(minutes=1),
    )

    call_command("process_reminders")
    reminder.refresh_from_db()
    assert reminder.status == Reminder.Status.CANCELLED
    assert "Consent not granted" in reminder.last_error


@pytest.mark.django_db
def test_process_reminders_defers_when_quiet_hours(clinic, patient, client_with_membership):
    now = timezone.now()
    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=1),
    )
    local_now = timezone.localtime(now)
    ReminderPreference.objects.create(
        clinic=clinic,
        client=client_with_membership,
        allow_email=True,
        preferred_channel=ReminderPreference.PreferredChannel.EMAIL,
        timezone="UTC",
        quiet_hours_start=(local_now - timedelta(hours=1)).time().replace(second=0, microsecond=0),
        quiet_hours_end=(local_now + timedelta(hours=1)).time().replace(second=0, microsecond=0),
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        invoice=invoice,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
        recipient="owner@example.com",
        scheduled_for=now - timedelta(minutes=1),
    )

    call_command("process_reminders")
    reminder.refresh_from_db()
    assert reminder.status == Reminder.Status.DEFERRED
    assert reminder.scheduled_for > now
