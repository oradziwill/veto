from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings


@pytest.mark.django_db
@override_settings(
    PORTAL_RETURN_OTP_IN_RESPONSE=True,
    PORTAL_OTP_REQUEST_LIMIT_PER_MAILBOX=2,
    PORTAL_OTP_REQUEST_MAILBOX_WINDOW_SEC=900,
    PORTAL_OTP_REQUEST_LIMIT_PER_IP=500,
)
def test_request_code_mailbox_rate_limit(api_client, clinic, client_with_membership):
    cache.clear()
    slug = clinic.slug
    email = client_with_membership.email
    url = "/api/portal/auth/request-code/"
    body = {"clinic_slug": slug, "email": email}
    assert api_client.post(url, body, format="json").status_code == 200
    assert api_client.post(url, body, format="json").status_code == 200
    assert api_client.post(url, body, format="json").status_code == 429


@pytest.mark.django_db
@override_settings(
    PORTAL_RETURN_OTP_IN_RESPONSE=True,
    PORTAL_OTP_CONFIRM_LIMIT_PER_MAILBOX=2,
    PORTAL_OTP_CONFIRM_MAILBOX_WINDOW_SEC=900,
    PORTAL_OTP_CONFIRM_LIMIT_PER_IP=500,
)
def test_confirm_code_mailbox_rate_limit(api_client, clinic, client_with_membership):
    cache.clear()
    slug = clinic.slug
    email = client_with_membership.email
    api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": email},
        format="json",
    )
    url = "/api/portal/auth/confirm-code/"
    bad = {"clinic_slug": slug, "email": email, "code": "000000"}
    assert api_client.post(url, bad, format="json").status_code == 400
    assert api_client.post(url, bad, format="json").status_code == 400
    assert api_client.post(url, bad, format="json").status_code == 429


@pytest.mark.django_db
@override_settings(
    PORTAL_RETURN_OTP_IN_RESPONSE=True,
    PORTAL_OTP_EMAIL_ENABLED=True,
    REMINDER_SENDGRID_API_KEY="sg.test",
    REMINDER_SENDGRID_FROM_EMAIL="noreply@example.com",
)
@patch("apps.portal.views_auth.send_portal_otp_email")
def test_request_code_sends_email_when_enabled(
    mock_send, api_client, clinic, client_with_membership
):
    cache.clear()
    slug = clinic.slug
    email = client_with_membership.email
    r = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": email},
        format="json",
    )
    assert r.status_code == 200
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to_email"] == email
    assert kwargs["clinic_name"] == clinic.name
    assert len(kwargs["code"]) == 6
    assert kwargs.get("magic_plain_token")
    assert kwargs.get("magic_link_url") is None
