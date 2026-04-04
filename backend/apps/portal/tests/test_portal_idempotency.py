import pytest
from django.test import override_settings

from apps.scheduling.models import Appointment


@pytest.fixture
def doctor_with_all_weekdays_hours(doctor):
    from datetime import time

    from apps.scheduling.models_working_hours import VetWorkingHours

    for wd in range(7):
        VetWorkingHours.objects.get_or_create(
            vet=doctor,
            weekday=wd,
            defaults={
                "start_time": time(9, 0),
                "end_time": time(17, 0),
                "is_active": True,
            },
        )
    return doctor


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_portal_booking_idempotency_replays_same_response(
    api_client,
    clinic,
    doctor_with_all_weekdays_hours,
    patient,
    client_with_membership,
):
    from django.utils import timezone

    slug = clinic.slug
    today = timezone.localdate().isoformat()

    api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": client_with_membership.email},
        format="json",
    )
    conf = api_client.post(
        "/api/portal/auth/confirm-code/",
        {
            "clinic_slug": slug,
            "email": client_with_membership.email,
            "code": api_client.post(
                "/api/portal/auth/request-code/",
                {"clinic_slug": slug, "email": client_with_membership.email},
                format="json",
            ).data["_dev_otp"],
        },
        format="json",
    )
    assert conf.status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {conf.data['access']}")

    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    slot = av.data["free"][0]

    body = {
        "patient_id": patient.id,
        "vet_id": doctor_with_all_weekdays_hours.id,
        "starts_at": slot["start"],
        "ends_at": slot["end"],
        "reason": "idem",
    }
    headers = {"HTTP_IDEMPOTENCY_KEY": "book-retry-1"}

    r1 = api_client.post("/api/portal/appointments/", body, format="json", **headers)
    assert r1.status_code == 201
    aid = r1.data["id"]

    r2 = api_client.post("/api/portal/appointments/", body, format="json", **headers)
    assert r2.status_code == 201
    assert r2.data["id"] == aid
    assert Appointment.objects.filter(pk=aid).count() == 1


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_portal_booking_idempotency_conflict_different_body(
    api_client,
    clinic,
    doctor_with_all_weekdays_hours,
    patient,
    client_with_membership,
):
    from django.utils import timezone

    slug = clinic.slug
    today = timezone.localdate().isoformat()

    api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": client_with_membership.email},
        format="json",
    )
    req = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": client_with_membership.email},
        format="json",
    )
    conf = api_client.post(
        "/api/portal/auth/confirm-code/",
        {
            "clinic_slug": slug,
            "email": client_with_membership.email,
            "code": req.data["_dev_otp"],
        },
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {conf.data['access']}")

    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    slot = av.data["free"][0]

    b1 = {
        "patient_id": patient.id,
        "vet_id": doctor_with_all_weekdays_hours.id,
        "starts_at": slot["start"],
        "ends_at": slot["end"],
        "reason": "first",
    }
    assert (
        api_client.post(
            "/api/portal/appointments/",
            b1,
            format="json",
            HTTP_IDEMPOTENCY_KEY="same-key-new-body",
        ).status_code
        == 201
    )

    b2 = {**b1, "reason": "second"}
    r2 = api_client.post(
        "/api/portal/appointments/",
        b2,
        format="json",
        HTTP_IDEMPOTENCY_KEY="same-key-new-body",
    )
    assert r2.status_code == 409


@pytest.mark.django_db
@override_settings(PORTAL_ALLOW_SIMULATED_PAYMENT=True, PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_portal_complete_deposit_simulated_idempotent(
    api_client,
    clinic,
    doctor_with_all_weekdays_hours,
    patient,
    client_with_membership,
):
    """Double submit complete-deposit with same key returns one payment."""
    from decimal import Decimal

    from django.utils import timezone

    from apps.billing.models import Invoice

    clinic.portal_booking_deposit_amount = Decimal("10.00")
    clinic.save(update_fields=["portal_booking_deposit_amount"])

    slug = clinic.slug
    today = timezone.localdate().isoformat()

    api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": client_with_membership.email},
        format="json",
    )
    req = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": client_with_membership.email},
        format="json",
    )
    conf = api_client.post(
        "/api/portal/auth/confirm-code/",
        {
            "clinic_slug": slug,
            "email": client_with_membership.email,
            "code": req.data["_dev_otp"],
        },
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {conf.data['access']}")

    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    slot = av.data["free"][0]
    book = api_client.post(
        "/api/portal/appointments/",
        {
            "patient_id": patient.id,
            "vet_id": doctor_with_all_weekdays_hours.id,
            "starts_at": slot["start"],
            "ends_at": slot["end"],
        },
        format="json",
    )
    assert book.status_code == 201
    inv_id = book.data["deposit_invoice_id"]
    assert inv_id

    url = f"/api/portal/invoices/{inv_id}/complete-deposit/"
    body = {"simulated": True}
    h = {"HTTP_IDEMPOTENCY_KEY": "pay-once"}

    r1 = api_client.post(url, body, format="json", **h)
    assert r1.status_code == 200
    r2 = api_client.post(url, body, format="json", **h)
    assert r2.status_code == 200
    inv = Invoice.objects.get(pk=inv_id)
    assert inv.payments.count() == 1


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_portal_booking_rejects_oversized_idempotency_key(
    api_client,
    clinic,
    doctor_with_all_weekdays_hours,
    patient,
    client_with_membership,
):
    from django.utils import timezone

    slug = clinic.slug
    today = timezone.localdate().isoformat()

    r = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": client_with_membership.email},
        format="json",
    )
    conf = api_client.post(
        "/api/portal/auth/confirm-code/",
        {
            "clinic_slug": slug,
            "email": client_with_membership.email,
            "code": r.data["_dev_otp"],
        },
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {conf.data['access']}")

    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    slot = av.data["free"][0]

    too_long = "x" * 129
    out = api_client.post(
        "/api/portal/appointments/",
        {
            "patient_id": patient.id,
            "vet_id": doctor_with_all_weekdays_hours.id,
            "starts_at": slot["start"],
            "ends_at": slot["end"],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=too_long,
    )
    assert out.status_code == 400
