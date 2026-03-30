import pytest
from django.test import override_settings


@pytest.mark.django_db
@override_settings(
    PORTAL_RETURN_OTP_IN_RESPONSE=True,
    PORTAL_OTP_CONFIRM_LIMIT_PER_MAILBOX=500,
    PORTAL_OTP_CONFIRM_MAILBOX_WINDOW_SEC=900,
    PORTAL_OTP_CONFIRM_LIMIT_PER_IP=500,
    PORTAL_CONFIRM_FAIL_LIMIT_MAILBOX=3,
    PORTAL_CONFIRM_FAIL_WINDOW_SEC=900,
    PORTAL_CONFIRM_LOCKOUT_SEC=900,
    PORTAL_CONFIRM_FAIL_LIMIT_IP=500,
)
def test_confirm_code_lockout_after_repeated_bad_codes(api_client, clinic, client_with_membership):
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
    assert api_client.post(url, bad, format="json").status_code == 400
    r = api_client.post(url, bad, format="json")
    assert r.status_code == 429
    assert "invalid code attempts" in (r.data.get("detail") or "").lower()
