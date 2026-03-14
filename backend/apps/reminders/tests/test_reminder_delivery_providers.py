from __future__ import annotations

import json
from datetime import timedelta
from urllib.error import HTTPError

import pytest
from django.utils import timezone

from apps.billing.models import Invoice
from apps.reminders import services
from apps.reminders.models import Reminder


class _FakeResponse:
    def __init__(self, *, status=202, headers=None, body="{}"):
        self.status = status
        self.headers = headers or {}
        self._body = body.encode("utf-8")

    def getcode(self):
        return self.status

    def read(self):
        return self._body


@pytest.mark.django_db
def test_sendgrid_provider_adapter_returns_message_id(
    clinic, patient, client_with_membership, monkeypatch, settings
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
        subject="Invoice reminder",
        body="Please pay",
        scheduled_for=timezone.now(),
    )
    settings.REMINDER_EMAIL_PROVIDER = "sendgrid"
    settings.REMINDER_SENDGRID_API_KEY = "sg-key"
    settings.REMINDER_SENDGRID_FROM_EMAIL = "noreply@example.com"
    settings.REMINDER_SENDGRID_FROM_NAME = "Veto"

    def _fake_urlopen(_req, timeout=15):
        return _FakeResponse(status=202, headers={"X-Message-Id": "sg-msg-1"})

    monkeypatch.setattr(services.request, "urlopen", _fake_urlopen)
    message_id, provider_status = services.send_reminder(reminder)
    assert message_id == "sg-msg-1"
    assert provider_status == "accepted"
    assert reminder.provider == Reminder.Provider.SENDGRID


@pytest.mark.django_db
def test_twilio_provider_adapter_returns_sid(
    clinic, patient, client_with_membership, monkeypatch, settings
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
        channel=Reminder.Channel.SMS,
        recipient="+48123123123",
        subject="Invoice reminder",
        body="Please pay",
        scheduled_for=timezone.now(),
    )
    settings.REMINDER_SMS_PROVIDER = "twilio"
    settings.REMINDER_TWILIO_ACCOUNT_SID = "AC123"
    settings.REMINDER_TWILIO_AUTH_TOKEN = "auth"
    settings.REMINDER_TWILIO_FROM_NUMBER = "+48999999999"

    def _fake_urlopen(_req, timeout=15):
        return _FakeResponse(status=201, body=json.dumps({"sid": "SM123", "status": "queued"}))

    monkeypatch.setattr(services.request, "urlopen", _fake_urlopen)
    message_id, provider_status = services.send_reminder(reminder)
    assert message_id == "SM123"
    assert provider_status == "queued"
    assert reminder.provider == Reminder.Provider.TWILIO


@pytest.mark.django_db
def test_sendgrid_http_error_raises_validation(
    clinic, patient, client_with_membership, monkeypatch, settings
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
        subject="Invoice reminder",
        body="Please pay",
        scheduled_for=timezone.now(),
    )
    settings.REMINDER_EMAIL_PROVIDER = "sendgrid"
    settings.REMINDER_SENDGRID_API_KEY = "sg-key"
    settings.REMINDER_SENDGRID_FROM_EMAIL = "noreply@example.com"

    def _fake_urlopen(_req, timeout=15):
        raise HTTPError(url="http://example.com", code=401, msg="Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr(services.request, "urlopen", _fake_urlopen)
    with pytest.raises(ValueError):
        services.send_reminder(reminder)
