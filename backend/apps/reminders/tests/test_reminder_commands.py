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
from apps.reminders.models import (
    Reminder,
    ReminderEscalationExecution,
    ReminderEscalationRule,
    ReminderEvent,
    ReminderInboundReply,
    ReminderPortalActionToken,
    ReminderPreference,
    ReminderTemplate,
)
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
    appointment_reminder = Reminder.objects.filter(
        reminder_type=Reminder.ReminderType.APPOINTMENT
    ).first()
    assert appointment_reminder is not None
    assert appointment_reminder.experiment_key == "appointment_copy_v1"
    assert appointment_reminder.experiment_variant in {"A", "B"}
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
def test_process_reminders_cancels_sms_when_reminder_sms_disabled(
    clinic, patient, client_with_membership
):
    clinic.reminder_sms_enabled = False
    clinic.save(update_fields=["reminder_sms_enabled"])
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
        channel=Reminder.Channel.SMS,
        recipient="+48123456789",
        subject="Pay",
        body="Please pay",
        scheduled_for=timezone.now() - timedelta(minutes=1),
    )

    call_command("process_reminders")
    reminder.refresh_from_db()
    assert reminder.status == Reminder.Status.CANCELLED
    assert "disabled for this clinic" in reminder.last_error
    ev = ReminderEvent.objects.filter(reminder=reminder).last()
    assert ev is not None
    assert ev.event_type == ReminderEvent.EventType.CANCELLED
    assert ev.payload.get("reason") == "reminder_sms_disabled"


@pytest.mark.django_db
def test_process_reminders_email_still_sent_when_sms_disabled(
    clinic, patient, client_with_membership
):
    clinic.reminder_sms_enabled = False
    clinic.save(update_fields=["reminder_sms_enabled"])
    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=1),
    )
    email_reminder = Reminder.objects.create(
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
    email_reminder.refresh_from_db()
    assert email_reminder.status == Reminder.Status.SENT


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


@pytest.mark.django_db
def test_enqueue_appointments_includes_portal_links_in_template(clinic, patient, doctor, settings):
    settings.REMINDER_PORTAL_BASE_URL = "https://portal.example.com"
    now = timezone.now()
    Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now + timedelta(hours=2),
        ends_at=now + timedelta(hours=2, minutes=30),
        status=Appointment.Status.SCHEDULED,
    )
    ReminderTemplate.objects.create(
        clinic=clinic,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        locale=ReminderTemplate.Locale.EN,
        subject_template="Confirm your visit",
        body_template=(
            "Confirm: {confirm_url}\nCancel: {cancel_url}\nReschedule: {reschedule_url}"
        ),
        is_active=True,
    )

    call_command("enqueue_reminders", appointment_hours=24)

    reminder = Reminder.objects.filter(reminder_type=Reminder.ReminderType.APPOINTMENT).first()
    assert reminder is not None
    assert "https://portal.example.com/api/reminders/portal/" in reminder.body
    assert ReminderPortalActionToken.objects.filter(reminder=reminder).count() == 3


@pytest.mark.django_db
def test_run_reminder_escalations_enqueues_followup_for_unconfirmed_appointment(
    clinic, patient, doctor
):
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=timezone.now() + timedelta(hours=4),
        ends_at=timezone.now() + timedelta(hours=5),
        status=Appointment.Status.SCHEDULED,
    )
    source = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        status=Reminder.Status.SENT,
        recipient="owner@example.com",
        subject="Please confirm appointment",
        body="Tap to confirm.",
        sent_at=timezone.now() - timedelta(minutes=180),
        scheduled_for=timezone.now() - timedelta(minutes=180),
    )
    ReminderEscalationRule.objects.create(
        clinic=clinic,
        name="Appt no confirmation 2h",
        trigger_type=ReminderEscalationRule.TriggerType.APPOINTMENT_UNCONFIRMED,
        delay_minutes=120,
        action_type=ReminderEscalationRule.ActionType.ENQUEUE_FOLLOWUP,
        max_executions_per_target=1,
    )

    call_command("run_reminder_escalations")

    followups = Reminder.objects.filter(
        clinic=clinic,
        appointment=appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
    ).exclude(id=source.id)
    assert followups.count() == 1
    followup = followups.first()
    assert followup is not None
    assert followup.subject.startswith("[Follow-up]")
    assert (
        ReminderEscalationExecution.objects.filter(
            reminder=source, status=ReminderEscalationExecution.Status.APPLIED
        ).count()
        == 1
    )

    call_command("run_reminder_escalations")
    assert ReminderEscalationExecution.objects.filter(reminder=source).count() == 1


@pytest.mark.django_db
def test_run_reminder_escalations_flags_unresolved_reschedule_reply(clinic, patient, doctor):
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=timezone.now() + timedelta(hours=8),
        ends_at=timezone.now() + timedelta(hours=9),
        status=Appointment.Status.SCHEDULED,
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.SMS,
        status=Reminder.Status.SENT,
        recipient="+48111111111",
        subject="Appointment reminder",
        body="Reply RESCHEDULE to change time.",
        sent_at=timezone.now() - timedelta(minutes=80),
        scheduled_for=timezone.now() - timedelta(minutes=80),
    )
    reply = ReminderInboundReply.objects.create(
        clinic=clinic,
        reminder=reminder,
        provider=Reminder.Provider.TWILIO,
        provider_reply_id="reply-escalation-1",
        provider_message_id="msg-1",
        raw_text="reschedule",
        normalized_intent=ReminderInboundReply.Intent.RESCHEDULE,
        action_status=ReminderInboundReply.ActionStatus.NEEDS_REVIEW,
    )
    ReminderEscalationRule.objects.create(
        clinic=clinic,
        name="Reschedule > 30m",
        trigger_type=ReminderEscalationRule.TriggerType.RESCHEDULE_UNRESOLVED,
        delay_minutes=0,
        action_type=ReminderEscalationRule.ActionType.FLAG_FOR_REVIEW,
        max_executions_per_target=2,
    )

    call_command("run_reminder_escalations")
    reply.refresh_from_db()

    assert "Escalated by automated playbook." in reply.action_note
    assert ReminderEscalationExecution.objects.filter(
        reminder=reminder, status=ReminderEscalationExecution.Status.APPLIED
    ).exists()
