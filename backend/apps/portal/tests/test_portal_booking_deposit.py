from datetime import time
from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.billing.models import Invoice
from apps.scheduling.models import Appointment
from apps.scheduling.models_working_hours import VetWorkingHours


def _otp_flow(api_client, clinic, email):
    clinic.refresh_from_db()
    slug = clinic.slug
    r = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": email},
        format="json",
    )
    assert r.status_code == 200
    code = r.data["_dev_otp"]
    c = api_client.post(
        "/api/portal/auth/confirm-code/",
        {"clinic_slug": slug, "email": email, "code": code},
        format="json",
    )
    assert c.status_code == 200
    return c.data["access"]


@pytest.fixture
def doctor_with_all_weekdays_hours(doctor):
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
@override_settings(
    PORTAL_RETURN_OTP_IN_RESPONSE=True,
    PORTAL_ALLOW_SIMULATED_PAYMENT=True,
    DEBUG=True,
)
def test_portal_booking_with_deposit_then_simulated_payment(
    api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
):
    clinic.portal_booking_deposit_amount = Decimal("50.00")
    clinic.portal_booking_deposit_line_label = "Zaliczka rezerwacja"
    clinic.save(
        update_fields=[
            "portal_booking_deposit_amount",
            "portal_booking_deposit_line_label",
        ]
    )

    slug = clinic.slug
    today = timezone.localdate().isoformat()
    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    slot = av.data["free"][0]

    access = _otp_flow(api_client, clinic, client_with_membership.email)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    book = api_client.post(
        "/api/portal/appointments/",
        {
            "patient_id": patient.id,
            "vet_id": doctor_with_all_weekdays_hours.id,
            "starts_at": slot["start"],
            "ends_at": slot["end"],
            "reason": "Deposit flow",
        },
        format="json",
    )
    assert book.status_code == 201
    assert book.data["status"] == Appointment.Status.SCHEDULED
    assert book.data["payment_required"] is True
    assert book.data["deposit_invoice_id"] is not None
    inv_id = book.data["deposit_invoice_id"]

    inv = Invoice.objects.get(pk=inv_id)
    assert inv.status == Invoice.Status.DRAFT

    pay = api_client.post(
        f"/api/portal/invoices/{inv_id}/complete-deposit/",
        {"simulated": True},
        format="json",
    )
    assert pay.status_code == 200
    assert pay.data["status"] == Appointment.Status.CONFIRMED
    assert pay.data["payment_required"] is False

    inv.refresh_from_db()
    assert inv.status == Invoice.Status.PAID

    assert AuditLog.objects.filter(
        action="portal_booking_deposit_paid",
        entity_id=str(book.data["id"]),
    ).exists()


@pytest.mark.django_db
@override_settings(
    PORTAL_RETURN_OTP_IN_RESPONSE=True,
    PORTAL_ALLOW_SIMULATED_PAYMENT=False,
    DEBUG=False,
)
def test_complete_deposit_rejects_simulated_when_disabled(
    api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
):
    clinic.portal_booking_deposit_amount = Decimal("10.00")
    clinic.save(update_fields=["portal_booking_deposit_amount"])

    slug = clinic.slug
    today = timezone.localdate().isoformat()
    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    slot = av.data["free"][0]
    access = _otp_flow(api_client, clinic, client_with_membership.email)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

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
    inv_id = book.data["deposit_invoice_id"]
    resp = api_client.post(
        f"/api/portal/invoices/{inv_id}/complete-deposit/",
        {"simulated": True},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
@override_settings(
    PORTAL_RETURN_OTP_IN_RESPONSE=True,
    PORTAL_ALLOW_SIMULATED_PAYMENT=True,
    STRIPE_SECRET_KEY="",
    STRIPE_WEBHOOK_SECRET="",
)
def test_complete_deposit_without_live_provider_returns_501(
    api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
):
    clinic.portal_booking_deposit_amount = Decimal("10.00")
    clinic.save(update_fields=["portal_booking_deposit_amount"])
    slug = clinic.slug
    today = timezone.localdate().isoformat()
    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    slot = av.data["free"][0]
    access = _otp_flow(api_client, clinic, client_with_membership.email)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
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
    inv_id = book.data["deposit_invoice_id"]
    resp = api_client.post(
        f"/api/portal/invoices/{inv_id}/complete-deposit/",
        {},
        format="json",
    )
    assert resp.status_code == 501


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True, STRIPE_SECRET_KEY="sk_test_dummy")
def test_complete_deposit_without_body_with_stripe_returns_400(
    api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
):
    clinic.portal_booking_deposit_amount = Decimal("10.00")
    clinic.save(update_fields=["portal_booking_deposit_amount"])
    slug = clinic.slug
    today = timezone.localdate().isoformat()
    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    slot = av.data["free"][0]
    access = _otp_flow(api_client, clinic, client_with_membership.email)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
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
    inv_id = book.data["deposit_invoice_id"]
    resp = api_client.post(
        f"/api/portal/invoices/{inv_id}/complete-deposit/",
        {},
        format="json",
    )
    assert resp.status_code == 400
