from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import Invoice
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from apps.reminders.models import (
    Reminder,
    ReminderEscalationExecution,
    ReminderEscalationRule,
    ReminderInboundReply,
    ReminderPortalActionToken,
    ReminderProviderConfig,
)
from apps.reminders.services import generate_portal_action_token
from apps.scheduling.models import Appointment
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


@pytest.mark.django_db
def test_reminder_metrics_clinic_scoped(
    api_client, receptionist, clinic, patient, client_with_membership
):
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
        provider=Reminder.Provider.INTERNAL,
        status=Reminder.Status.QUEUED,
        recipient="owner@example.com",
        scheduled_for=timezone.now() - timedelta(minutes=10),
    )
    Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        invoice=invoice,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.SENDGRID,
        status=Reminder.Status.FAILED,
        recipient="owner@example.com",
        scheduled_for=timezone.now(),
    )

    other_clinic = Clinic.objects.create(
        name="Clinic Metrics B",
        address="Street 12",
        phone="+48999999999",
        email="metrics-b@example.com",
    )
    other_owner = Client.objects.create(
        first_name="Other", last_name="Owner", email="other.metrics@example.com"
    )
    ClientClinic.objects.create(client=other_owner, clinic=other_clinic, is_active=True)
    other_doctor = User.objects.create_user(
        username="doctor_other_metrics",
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
        provider=Reminder.Provider.TWILIO,
        status=Reminder.Status.FAILED,
        recipient="other@example.com",
        scheduled_for=timezone.now(),
    )

    api_client.force_authenticate(user=receptionist)
    response = api_client.get("/api/reminders/metrics/")
    assert response.status_code == 200
    assert response.data["kind"] == "reminder_metrics_snapshot"
    assert response.data["status_counts"]["queued"] == 1
    assert response.data["status_counts"]["failed"] == 1
    assert response.data["provider_counts"].get(Reminder.Provider.INTERNAL) == 1
    assert response.data["provider_counts"].get(Reminder.Provider.SENDGRID) == 1
    assert response.data["provider_counts"].get(Reminder.Provider.TWILIO, 0) == 0
    assert response.data["failed_last_24h"] == 1
    assert response.data["oldest_queued_age_seconds"] >= 0


@pytest.mark.django_db
def test_reminder_metrics_requires_authentication(api_client):
    response = api_client.get("/api/reminders/metrics/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_reminder_analytics_clinic_scoped_and_filtered(
    api_client, clinic_admin, clinic, patient, client_with_membership
):
    now = timezone.now()
    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.SENT,
        due_date=timezone.localdate() + timedelta(days=1),
    )
    delivered = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        invoice=invoice,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.SENDGRID,
        status=Reminder.Status.SENT,
        recipient="owner@example.com",
        scheduled_for=now,
        delivered_at=now,
    )
    Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        invoice=invoice,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.SENDGRID,
        status=Reminder.Status.FAILED,
        recipient="owner@example.com",
        scheduled_for=now,
    )
    Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        invoice=invoice,
        reminder_type=Reminder.ReminderType.INVOICE,
        channel=Reminder.Channel.SMS,
        provider=Reminder.Provider.TWILIO,
        status=Reminder.Status.CANCELLED,
        recipient="+48111111111",
        scheduled_for=now,
    )

    other_clinic = Clinic.objects.create(
        name="Clinic Analytics B",
        address="Street 12",
        phone="+48888888888",
        email="analytics-b@example.com",
    )
    other_owner = Client.objects.create(
        first_name="Other", last_name="Owner", email="other.analytics@example.com"
    )
    ClientClinic.objects.create(client=other_owner, clinic=other_clinic, is_active=True)
    other_doctor = User.objects.create_user(
        username="doctor_other_analytics",
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
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.SENDGRID,
        status=Reminder.Status.SENT,
        recipient="other@example.com",
        scheduled_for=now,
        delivered_at=now,
    )

    from_str = (timezone.localdate() - timedelta(days=1)).isoformat()
    to_str = (timezone.localdate() + timedelta(days=1)).isoformat()
    api_client.force_authenticate(user=clinic_admin)
    response = api_client.get(
        "/api/reminders/analytics/",
        {
            "period": "daily",
            "from": from_str,
            "to": to_str,
            "channel": "email",
            "provider": "sendgrid",
            "type": "appointment",
        },
    )
    assert response.status_code == 200
    assert response.data["kind"] == "reminder_analytics"
    assert response.data["totals"]["total"] == 2
    assert response.data["totals"]["delivered"] == 1
    assert response.data["totals"]["failed"] == 1
    assert response.data["totals"]["cancelled"] == 0
    assert response.data["rates"]["delivery_rate"] == 0.5
    assert response.data["filters"] == {
        "channel": "email",
        "provider": "sendgrid",
        "type": "appointment",
    }
    labels = [row["label"] for row in response.data["by_period"]]
    assert from_str in labels and to_str in labels
    today_bucket = next(
        row
        for row in response.data["by_period"]
        if row["label"] == timezone.localdate().isoformat()
    )
    assert today_bucket["total"] == 2
    assert today_bucket["delivered"] == 1

    # sanity check the delivered reminder belongs to the authenticated clinic data only
    assert delivered.clinic_id == clinic_admin.clinic_id


@pytest.mark.django_db
def test_reminder_analytics_requires_authentication(api_client):
    response = api_client.get("/api/reminders/analytics/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_reminder_analytics_requires_admin(api_client, receptionist):
    api_client.force_authenticate(user=receptionist)
    response = api_client.get("/api/reminders/analytics/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_reminder_analytics_rejects_invalid_period(api_client, clinic_admin):
    api_client.force_authenticate(user=clinic_admin)
    response = api_client.get("/api/reminders/analytics/", {"period": "weekly"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_reminder_experiment_attribution_groups_variants_and_outcomes(
    api_client, clinic_admin, clinic, patient, doctor
):
    now = timezone.now()
    appt_a = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, minutes=30),
        status=Appointment.Status.COMPLETED,
        reason="Control check",
    )
    appt_b = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=2, minutes=30),
        status=Appointment.Status.NO_SHOW,
        reason="Variant check",
    )
    Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appt_a,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.SENDGRID,
        status=Reminder.Status.SENT,
        recipient="owner@example.com",
        scheduled_for=now,
        delivered_at=now,
        experiment_key="appointment_copy_v1",
        experiment_variant="A",
    )
    Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appt_b,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.SENDGRID,
        status=Reminder.Status.SENT,
        recipient="owner@example.com",
        scheduled_for=now,
        experiment_key="appointment_copy_v1",
        experiment_variant="B",
    )

    api_client.force_authenticate(user=clinic_admin)
    response = api_client.get(
        "/api/reminders/experiment-attribution/",
        {"minimum_sample_size": 2, "channel": "email", "provider": "sendgrid"},
    )
    assert response.status_code == 200
    assert response.data["kind"] == "reminder_experiment_attribution"
    assert response.data["overall"]["appointments_total"] == 2
    assert response.data["overall"]["appointments_no_show"] == 1
    assert response.data["overall"]["no_show_rate"] == 0.5
    variants = {row["variant"]: row for row in response.data["variants"]}
    assert variants["A"]["appointments_completed"] == 1
    assert variants["A"]["appointments_no_show"] == 0
    assert variants["A"]["sample_warning"] is True
    assert variants["B"]["appointments_completed"] == 0
    assert variants["B"]["appointments_no_show"] == 1
    assert variants["B"]["no_show_rate"] == 1.0


@pytest.mark.django_db
def test_reminder_experiment_attribution_requires_admin(api_client, receptionist):
    api_client.force_authenticate(user=receptionist)
    response = api_client.get("/api/reminders/experiment-attribution/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_reminder_preferences_crud_clinic_scoped(
    api_client, receptionist, clinic_admin, clinic, client_with_membership
):
    api_client.force_authenticate(user=clinic_admin)
    create = api_client.post(
        "/api/reminder-preferences/",
        {
            "client": client_with_membership.id,
            "allow_email": True,
            "allow_sms": False,
            "preferred_channel": "email",
            "timezone": "UTC",
            "quiet_hours_start": "22:00:00",
            "quiet_hours_end": "08:00:00",
        },
        format="json",
    )
    assert create.status_code == 201
    pref_id = create.data["id"]

    api_client.force_authenticate(user=receptionist)
    list_response = api_client.get("/api/reminder-preferences/")
    assert list_response.status_code == 200
    assert any(row["id"] == pref_id for row in list_response.data)

    api_client.force_authenticate(user=clinic_admin)
    patch = api_client.patch(
        f"/api/reminder-preferences/{pref_id}/",
        {"allow_sms": True, "preferred_channel": "sms"},
        format="json",
    )
    assert patch.status_code == 200
    assert patch.data["allow_sms"] is True
    assert patch.data["preferred_channel"] == "sms"


@pytest.mark.django_db
def test_webhook_updates_reminder_status(api_client, clinic, patient, client_with_membership):
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
        provider_message_id="email-123",
        provider_status="accepted",
        recipient="owner@example.com",
        scheduled_for=timezone.now(),
        status=Reminder.Status.SENT,
    )

    response = api_client.post(
        "/api/reminders/webhooks/sendgrid/",
        {"message_id": "email-123", "status": "delivered"},
        format="json",
    )
    assert response.status_code == 200
    reminder.refresh_from_db()
    assert reminder.status == Reminder.Status.SENT
    assert reminder.provider_status == "delivered"
    assert reminder.delivered_at is not None


@pytest.mark.django_db
def test_webhook_signature_required_when_secret_set(
    api_client, clinic, patient, client_with_membership, settings
):
    settings.REMINDER_SENDGRID_WEBHOOK_SECRET = "secret"
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
        provider_message_id="email-999",
        provider_status="accepted",
        recipient="owner@example.com",
        scheduled_for=timezone.now(),
        status=Reminder.Status.SENT,
    )
    response = api_client.post(
        "/api/reminders/webhooks/sendgrid/",
        {"message_id": "email-999", "status": "delivered"},
        format="json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_webhook_sendgrid_signature_and_event_list(
    api_client, clinic, patient, client_with_membership, settings
):
    settings.REMINDER_SENDGRID_WEBHOOK_SECRET = "secret"
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
        provider_message_id="sg-event-1",
        provider_status="accepted",
        recipient="owner@example.com",
        scheduled_for=timezone.now(),
        status=Reminder.Status.SENT,
    )
    timestamp = "1710000000"
    raw = '[{"sg_message_id":"sg-event-1.filter1","event":"delivered"}]'
    signature = hmac.new(
        b"secret",
        f"{timestamp}.{raw}".encode(),
        hashlib.sha256,
    ).hexdigest()
    response = api_client.post(
        "/api/reminders/webhooks/sendgrid/",
        raw,
        content_type="application/json",
        HTTP_X_WEBHOOK_TIMESTAMP=timestamp,
        HTTP_X_WEBHOOK_SIGNATURE=signature,
    )
    assert response.status_code == 200
    reminder.refresh_from_db()
    assert reminder.provider_status == "delivered"
    assert reminder.delivered_at is not None


@pytest.mark.django_db
def test_reply_webhook_confirm_updates_appointment_and_is_idempotent(
    api_client, clinic, patient, client_with_membership, doctor
):
    now = timezone.now()
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, minutes=30),
        status=Appointment.Status.SCHEDULED,
        reason="Checkup",
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.SMS,
        provider=Reminder.Provider.TWILIO,
        provider_message_id="tw-message-1",
        recipient="+48111111111",
        scheduled_for=now,
        status=Reminder.Status.SENT,
    )

    payload = {
        "SmsSid": "tw-reply-1",
        "OriginalRepliedMessageSid": "tw-message-1",
        "Body": "YES",
    }
    response = api_client.post("/api/reminders/replies/twilio/", payload, format="json")
    assert response.status_code == 200
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED
    reply = ReminderInboundReply.objects.get(reminder=reminder)
    assert reply.normalized_intent == ReminderInboundReply.Intent.CONFIRM
    assert reply.action_status == ReminderInboundReply.ActionStatus.APPLIED

    duplicate = api_client.post("/api/reminders/replies/twilio/", payload, format="json")
    assert duplicate.status_code == 200
    assert duplicate.data["duplicates"] == 1
    assert ReminderInboundReply.objects.filter(reminder=reminder).count() == 1


@pytest.mark.django_db
def test_reply_webhook_reschedule_creates_unresolved_item(api_client, clinic, patient, doctor):
    now = timezone.now()
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=2, minutes=30),
        status=Appointment.Status.CONFIRMED,
        reason="Follow-up",
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.SENDGRID,
        provider_message_id="sg-message-1",
        recipient="owner@example.com",
        scheduled_for=now,
        status=Reminder.Status.SENT,
    )

    response = api_client.post(
        "/api/reminders/replies/sendgrid/",
        {"reply_id": "sg-reply-1", "message_id": "sg-message-1", "text": "reschedule"},
        format="json",
    )
    assert response.status_code == 200
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED
    reply = ReminderInboundReply.objects.get(reminder=reminder)
    assert reply.normalized_intent == ReminderInboundReply.Intent.RESCHEDULE
    assert reply.action_status == ReminderInboundReply.ActionStatus.NEEDS_REVIEW
    assert reply.resolved_at is None


@pytest.mark.django_db
def test_reminder_replies_list_requires_auth_and_is_clinic_scoped(
    api_client, receptionist, clinic, patient, doctor
):
    now = timezone.now()
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now + timedelta(days=3),
        ends_at=now + timedelta(days=3, minutes=30),
        status=Appointment.Status.SCHEDULED,
        reason="Scope check",
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.SENDGRID,
        provider_message_id="scope-message-1",
        recipient="owner@example.com",
        scheduled_for=now,
        status=Reminder.Status.SENT,
    )
    own_reply = ReminderInboundReply.objects.create(
        clinic=clinic,
        reminder=reminder,
        provider=Reminder.Provider.SENDGRID,
        provider_reply_id="scope-reply-1",
        provider_message_id="scope-message-1",
        raw_text="reschedule",
        normalized_intent=ReminderInboundReply.Intent.RESCHEDULE,
        action_status=ReminderInboundReply.ActionStatus.NEEDS_REVIEW,
    )

    other_clinic = Clinic.objects.create(
        name="Clinic D",
        address="Street 4",
        phone="+48444444444",
        email="d@example.com",
    )
    other_owner = Client.objects.create(
        first_name="Other", last_name="Owner", email="other.reply@example.com"
    )
    ClientClinic.objects.create(client=other_owner, clinic=other_clinic, is_active=True)
    other_doctor = User.objects.create_user(
        username="doctor_other_replies",
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
    other_appointment = Appointment.objects.create(
        clinic=other_clinic,
        patient=other_patient,
        vet=other_doctor,
        starts_at=now + timedelta(days=4),
        ends_at=now + timedelta(days=4, minutes=30),
        status=Appointment.Status.SCHEDULED,
        reason="Other scope",
    )
    other_reminder = Reminder.objects.create(
        clinic=other_clinic,
        patient=other_patient,
        appointment=other_appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.SENDGRID,
        provider_message_id="scope-message-2",
        recipient="other@example.com",
        scheduled_for=now,
        status=Reminder.Status.SENT,
    )
    ReminderInboundReply.objects.create(
        clinic=other_clinic,
        reminder=other_reminder,
        provider=Reminder.Provider.SENDGRID,
        provider_reply_id="scope-reply-2",
        provider_message_id="scope-message-2",
        raw_text="reschedule",
        normalized_intent=ReminderInboundReply.Intent.RESCHEDULE,
        action_status=ReminderInboundReply.ActionStatus.NEEDS_REVIEW,
    )

    unauth = api_client.get("/api/reminder-replies/")
    assert unauth.status_code == 401

    api_client.force_authenticate(user=receptionist)
    scoped = api_client.get("/api/reminder-replies/")
    assert scoped.status_code == 200
    returned_ids = {row["id"] for row in scoped.data}
    assert own_reply.id in returned_ids
    assert len(returned_ids) == 1


@pytest.mark.django_db
def test_portal_action_confirm_preview_and_execute(api_client, clinic, patient, doctor):
    now = timezone.now()
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now + timedelta(days=1),
        ends_at=now + timedelta(days=1, minutes=30),
        status=Appointment.Status.SCHEDULED,
        reason="Portal confirm",
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.INTERNAL,
        provider_message_id="portal-msg-1",
        recipient="owner@example.com",
        scheduled_for=now,
        status=Reminder.Status.SENT,
    )
    token = generate_portal_action_token(reminder, ReminderPortalActionToken.Action.CONFIRM)

    preview = api_client.get(f"/api/reminders/portal/{token}/")
    assert preview.status_code == 200
    assert preview.data["token_action"] == ReminderPortalActionToken.Action.CONFIRM
    assert preview.data["appointment"]["status"] == Appointment.Status.SCHEDULED

    execute = api_client.post(f"/api/reminders/portal/{token}/", {}, format="json")
    assert execute.status_code == 200
    assert execute.data["action_status"] == "applied"
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED

    reused = api_client.post(f"/api/reminders/portal/{token}/", {}, format="json")
    assert reused.status_code == 410


@pytest.mark.django_db
def test_portal_action_expired_token_returns_410(api_client, clinic, patient, doctor):
    now = timezone.now()
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=2, minutes=30),
        status=Appointment.Status.SCHEDULED,
        reason="Portal expired",
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        appointment=appointment,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        provider=Reminder.Provider.INTERNAL,
        provider_message_id="portal-msg-2",
        recipient="owner@example.com",
        scheduled_for=now,
        status=Reminder.Status.SENT,
    )
    token = generate_portal_action_token(
        reminder, ReminderPortalActionToken.Action.RESCHEDULE_REQUEST
    )
    token_row = ReminderPortalActionToken.objects.get(reminder=reminder)
    token_row.expires_at = now - timedelta(minutes=1)
    token_row.save(update_fields=["expires_at", "updated_at"])

    expired = api_client.post(f"/api/reminders/portal/{token}/", {}, format="json")
    assert expired.status_code == 410


@pytest.mark.django_db
def test_reminder_preferences_write_requires_admin(
    api_client, receptionist, client_with_membership
):
    api_client.force_authenticate(user=receptionist)
    response = api_client.post(
        "/api/reminder-preferences/",
        {
            "client": client_with_membership.id,
            "allow_email": True,
            "allow_sms": False,
            "preferred_channel": "email",
            "timezone": "UTC",
        },
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_reminder_provider_configs_permissions_and_clinic_scoped(
    api_client, clinic_admin, receptionist, clinic, settings
):
    settings.REMINDER_SENDGRID_API_KEY = "sg-key"
    settings.REMINDER_SENDGRID_FROM_EMAIL = "noreply@example.com"
    settings.REMINDER_SENDGRID_WEBHOOK_SECRET = "sg-secret"

    api_client.force_authenticate(user=clinic_admin)
    create = api_client.post(
        "/api/reminder-provider-configs/",
        {"email_provider": "sendgrid", "sms_provider": "internal"},
        format="json",
    )
    assert create.status_code == 201
    config_id = create.data["id"]

    api_client.force_authenticate(user=receptionist)
    list_response = api_client.get("/api/reminder-provider-configs/")
    assert list_response.status_code == 200
    assert [row["id"] for row in list_response.data] == [config_id]

    forbidden = api_client.post(
        "/api/reminder-provider-configs/",
        {"email_provider": "internal", "sms_provider": "twilio"},
        format="json",
    )
    assert forbidden.status_code == 403

    other_clinic = Clinic.objects.create(
        name="Clinic C",
        address="Street 3",
        phone="+48333333333",
        email="c@example.com",
    )
    other_admin = User.objects.create_user(
        username="other_admin_provider_cfg",
        password="pass",
        clinic=other_clinic,
        role=User.Role.ADMIN,
        is_staff=True,
    )
    other_config = ReminderProviderConfig.objects.create(
        clinic=other_clinic,
        email_provider=ReminderProviderConfig.EmailProvider.INTERNAL,
        sms_provider=ReminderProviderConfig.SmsProvider.INTERNAL,
        updated_by=other_admin,
    )
    list_response = api_client.get("/api/reminder-provider-configs/")
    returned_ids = {row["id"] for row in list_response.data}
    assert config_id in returned_ids
    assert other_config.id not in returned_ids


@pytest.mark.django_db
def test_reminder_provider_configs_validate_external_provider_requirements(
    api_client, clinic_admin, settings
):
    settings.REMINDER_SENDGRID_API_KEY = ""
    settings.REMINDER_SENDGRID_FROM_EMAIL = ""
    settings.REMINDER_SENDGRID_WEBHOOK_SECRET = ""

    api_client.force_authenticate(user=clinic_admin)
    invalid = api_client.post(
        "/api/reminder-provider-configs/",
        {"email_provider": "sendgrid", "sms_provider": "internal"},
        format="json",
    )
    assert invalid.status_code == 400
    assert invalid.data["code"] == "validation_error"
    assert "REMINDER_SENDGRID_API_KEY" in invalid.data["details"]["missing_settings"]

    settings.REMINDER_SENDGRID_API_KEY = "sg-key"
    settings.REMINDER_SENDGRID_FROM_EMAIL = "noreply@example.com"
    settings.REMINDER_SENDGRID_WEBHOOK_SECRET = "sg-secret"
    settings.REMINDER_TWILIO_ACCOUNT_SID = "AC123"
    settings.REMINDER_TWILIO_AUTH_TOKEN = "auth"
    settings.REMINDER_TWILIO_FROM_NUMBER = "+48111111111"
    settings.REMINDER_TWILIO_WEBHOOK_SECRET = "tw-secret"

    valid = api_client.post(
        "/api/reminder-provider-configs/",
        {"email_provider": "sendgrid", "sms_provider": "twilio"},
        format="json",
    )
    assert valid.status_code == 201
    assert valid.data["email_provider"] == "sendgrid"
    assert valid.data["sms_provider"] == "twilio"


@pytest.mark.django_db
def test_reminder_escalation_rule_crud_permissions(api_client, clinic_admin, receptionist, clinic):
    api_client.force_authenticate(user=receptionist)
    forbidden = api_client.post(
        "/api/reminder-escalation-rules/",
        {
            "name": "No confirm after 120m",
            "trigger_type": "appointment_unconfirmed",
            "delay_minutes": 120,
            "action_type": "enqueue_followup",
            "is_active": True,
            "max_executions_per_target": 1,
        },
        format="json",
    )
    assert forbidden.status_code == 403

    api_client.force_authenticate(user=clinic_admin)
    created = api_client.post(
        "/api/reminder-escalation-rules/",
        {
            "name": "No confirm after 120m",
            "trigger_type": "appointment_unconfirmed",
            "delay_minutes": 120,
            "action_type": "enqueue_followup",
            "is_active": True,
            "max_executions_per_target": 1,
        },
        format="json",
    )
    assert created.status_code == 201
    rule_id = created.data["id"]
    assert created.data["clinic"] == clinic.id

    api_client.force_authenticate(user=receptionist)
    listing = api_client.get("/api/reminder-escalation-rules/")
    assert listing.status_code == 200
    assert {row["id"] for row in listing.data} == {rule_id}


@pytest.mark.django_db
def test_reminder_escalation_metrics_admin_only_and_scoped(
    api_client, clinic_admin, receptionist, clinic, patient
):
    rule = ReminderEscalationRule.objects.create(
        clinic=clinic,
        name="Metrics rule",
        trigger_type=ReminderEscalationRule.TriggerType.APPOINTMENT_UNCONFIRMED,
        delay_minutes=30,
        action_type=ReminderEscalationRule.ActionType.ENQUEUE_FOLLOWUP,
    )
    reminder = Reminder.objects.create(
        clinic=clinic,
        patient=patient,
        reminder_type=Reminder.ReminderType.APPOINTMENT,
        channel=Reminder.Channel.EMAIL,
        status=Reminder.Status.SENT,
        recipient="owner@example.com",
        scheduled_for=timezone.now(),
    )
    ReminderEscalationExecution.objects.create(
        clinic=clinic,
        rule=rule,
        reminder=reminder,
        target_key=f"appointment:{reminder.appointment_id or reminder.id}",
        status=ReminderEscalationExecution.Status.APPLIED,
    )

    api_client.force_authenticate(user=receptionist)
    forbidden = api_client.get("/api/reminder-escalation-metrics/")
    assert forbidden.status_code == 403

    api_client.force_authenticate(user=clinic_admin)
    metrics = api_client.get("/api/reminder-escalation-metrics/")
    assert metrics.status_code == 200
    assert metrics.data["kind"] == "reminder_escalation_metrics"
    assert metrics.data["applied_total"] == 1
