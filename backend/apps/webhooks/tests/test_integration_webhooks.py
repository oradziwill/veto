from unittest.mock import MagicMock, patch

import pytest
from apps.audit.services import log_audit_event
from apps.webhooks.models import WebhookDelivery, WebhookEventType, WebhookSubscription
from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
def test_webhook_subscription_crud(api_client, clinic_admin, clinic):
    api_client.force_authenticate(user=clinic_admin)
    url = reverse("webhook-subscriptions-list")
    create = api_client.post(
        url,
        {
            "target_url": "https://example.com/hook",
            "description": "test",
            "secret": "hunter2",
            "event_types": [WebhookEventType.PORTAL_APPOINTMENT_BOOKED],
            "is_active": True,
        },
        format="json",
    )
    assert create.status_code == 201
    wid = create.data["id"]
    assert "secret" not in create.data

    lst = api_client.get(url)
    assert lst.status_code == 200
    assert len(lst.data) == 1
    assert lst.data[0]["target_url"] == "https://example.com/hook"
    assert "secret" not in lst.data[0]

    detail = api_client.get(reverse("webhook-subscriptions-detail", args=[wid]))
    assert detail.status_code == 200


@pytest.mark.django_db
def test_receptionist_cannot_manage_webhooks(api_client, receptionist, clinic):
    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        reverse("webhook-subscriptions-list"),
        {
            "target_url": "https://example.com/hook",
            "event_types": [WebhookEventType.INVOICE_PAYMENT_RECORDED],
        },
        format="json",
    )
    assert r.status_code == 403


@pytest.mark.django_db
@override_settings(WEBHOOK_DELIVERY_USE_THREAD=False)
def test_audit_triggers_webhook_delivery(clinic, clinic_admin):
    sub = WebhookSubscription.objects.create(
        clinic=clinic,
        target_url="https://httpbin.org/post",
        event_types=[WebhookEventType.PORTAL_APPOINTMENT_BOOKED],
        secret="s3cr3t",
        is_active=True,
        created_by=clinic_admin,
    )
    inner = MagicMock()
    inner.read.return_value = b"ok"
    inner.status = 200
    cm = MagicMock()
    cm.__enter__.return_value = inner
    cm.__exit__.return_value = None

    with patch("apps.webhooks.dispatch.urllib.request.urlopen", return_value=cm):
        log_audit_event(
            clinic_id=clinic.id,
            actor=None,
            action=WebhookEventType.PORTAL_APPOINTMENT_BOOKED,
            entity_type="appointment",
            entity_id="99",
            after={"x": 1},
            metadata={"source": "portal"},
        )

    d = WebhookDelivery.objects.filter(subscription=sub).first()
    assert d is not None
    assert d.status == WebhookDelivery.Status.DELIVERED
    assert d.http_status == 200
    assert d.payload["event"] == WebhookEventType.PORTAL_APPOINTMENT_BOOKED


@pytest.mark.django_db
def test_wrong_event_not_dispatched(clinic, clinic_admin):
    WebhookSubscription.objects.create(
        clinic=clinic,
        target_url="https://example.com/hook",
        event_types=[WebhookEventType.INVOICE_PAYMENT_RECORDED],
        is_active=True,
        created_by=clinic_admin,
    )
    log_audit_event(
        clinic_id=clinic.id,
        actor=None,
        action=WebhookEventType.PORTAL_APPOINTMENT_BOOKED,
        entity_type="appointment",
        entity_id="1",
        after={},
        metadata={},
    )
    assert WebhookDelivery.objects.count() == 0
