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
from apps.reminders.models import Reminder, ReminderProviderConfig
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
