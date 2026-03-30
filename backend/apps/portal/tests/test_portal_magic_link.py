import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.portal.models import PortalLoginChallenge


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_magic_link_returns_access(api_client, clinic, client_with_membership):
    cache.clear()
    slug = clinic.slug
    email = client_with_membership.email
    r = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": email},
        format="json",
    )
    assert r.status_code == 200
    token = r.data["_dev_magic_link_token"]
    assert len(token) >= 32

    m = api_client.post(
        "/api/portal/auth/magic-link/",
        {"token": token},
        format="json",
    )
    assert m.status_code == 200
    assert "access" in m.data


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_magic_link_cannot_be_reused(api_client, clinic, client_with_membership):
    cache.clear()
    slug = clinic.slug
    email = client_with_membership.email
    r = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": email},
        format="json",
    )
    token = r.data["_dev_magic_link_token"]
    assert (
        api_client.post("/api/portal/auth/magic-link/", {"token": token}, format="json").status_code
        == 200
    )
    assert (
        api_client.post("/api/portal/auth/magic-link/", {"token": token}, format="json").status_code
        == 400
    )


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_confirm_code_fails_after_magic_consumed(api_client, clinic, client_with_membership):
    cache.clear()
    slug = clinic.slug
    email = client_with_membership.email
    r = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": email},
        format="json",
    )
    code = r.data["_dev_otp"]
    token = r.data["_dev_magic_link_token"]
    assert (
        api_client.post(
            "/api/portal/auth/magic-link/",
            {"token": token},
            format="json",
        ).status_code
        == 200
    )
    conf = api_client.post(
        "/api/portal/auth/confirm-code/",
        {"clinic_slug": slug, "email": email, "code": code},
        format="json",
    )
    assert conf.status_code == 400


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_request_code_stores_magic_digest(api_client, clinic, client_with_membership):
    cache.clear()
    slug = clinic.slug
    api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": client_with_membership.email},
        format="json",
    )
    ch = PortalLoginChallenge.objects.order_by("-id").first()
    assert ch is not None
    assert len(ch.magic_token_digest) == 64
