from datetime import time
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.billing.models import Invoice
from apps.scheduling.models import Appointment
from apps.scheduling.models_working_hours import VetWorkingHours

from .test_portal_booking_deposit import _otp_flow


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


def _book_deposit_appointment(
    api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
):
    clinic.portal_booking_deposit_amount = Decimal("40.00")
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
    assert book.status_code == 201
    return book


@pytest.mark.django_db
@override_settings(
    PORTAL_RETURN_OTP_IN_RESPONSE=True,
    STRIPE_SECRET_KEY="sk_test_dummy",
)
def test_portal_stripe_checkout_returns_session(
    api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
):
    book = _book_deposit_appointment(
        api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
    )
    inv_id = book.data["deposit_invoice_id"]

    class FakeSession:
        url = "https://checkout.stripe.example/pay"
        id = "cs_test_123"

    with patch("stripe.checkout.Session.create", return_value=FakeSession()):
        r = api_client.post(
            f"/api/portal/invoices/{inv_id}/stripe-checkout/",
            {
                "success_url": "https://app.test/success",
                "cancel_url": "https://app.test/cancel",
            },
            format="json",
        )
    assert r.status_code == 200
    assert r.data["checkout_url"] == "https://checkout.stripe.example/pay"
    assert r.data["session_id"] == "cs_test_123"


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True, STRIPE_SECRET_KEY="sk_test_dummy")
def test_portal_complete_deposit_with_stripe_session(
    api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
):
    book = _book_deposit_appointment(
        api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
    )
    inv_id = book.data["deposit_invoice_id"]
    appt_id = book.data["id"]
    inv = Invoice.objects.get(pk=inv_id)
    from apps.portal.services.stripe_deposit import invoice_pln_gross_minor

    minor = invoice_pln_gross_minor(inv)
    meta = {
        "invoice_id": str(inv_id),
        "appointment_id": str(appt_id),
        "clinic_id": str(clinic.id),
    }

    class FakeSession:
        id = "cs_live_confirm"
        payment_status = "paid"
        amount_total = minor
        metadata = meta

    with patch("stripe.checkout.Session.retrieve", return_value=FakeSession()):
        pay = api_client.post(
            f"/api/portal/invoices/{inv_id}/complete-deposit/",
            {"stripe_session_id": "cs_live_confirm"},
            format="json",
        )
    assert pay.status_code == 200
    assert pay.data["status"] == Appointment.Status.CONFIRMED
    assert pay.data["payment_required"] is False
    inv.refresh_from_db()
    assert inv.status == Invoice.Status.PAID
    assert AuditLog.objects.filter(
        action="portal_booking_deposit_paid",
        entity_id=str(appt_id),
    ).exists()


@pytest.mark.django_db
@override_settings(
    PORTAL_RETURN_OTP_IN_RESPONSE=True,
    STRIPE_WEBHOOK_SECRET="whsec_test",
)
def test_stripe_webhook_completes_deposit(
    api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
):
    book = _book_deposit_appointment(
        api_client, clinic, doctor_with_all_weekdays_hours, patient, client_with_membership
    )
    inv_id = book.data["deposit_invoice_id"]
    appt_id = book.data["id"]
    inv = Invoice.objects.get(pk=inv_id)
    from apps.portal.services.stripe_deposit import invoice_pln_gross_minor

    minor = invoice_pln_gross_minor(inv)
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_wh_1",
                "payment_status": "paid",
                "amount_total": minor,
                "metadata": {
                    "invoice_id": str(inv_id),
                    "appointment_id": str(appt_id),
                    "clinic_id": str(clinic.id),
                },
            }
        },
    }
    api_client.credentials()  # webhook is unauthenticated
    with patch("stripe.Webhook.construct_event", return_value=event):
        r = api_client.post(
            "/api/portal/stripe/webhook/",
            b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=0,v1=test",
        )
    assert r.status_code == 200
    inv.refresh_from_db()
    assert inv.status == Invoice.Status.PAID
    wh_logs = AuditLog.objects.filter(
        action="portal_booking_deposit_paid",
        entity_id=str(appt_id),
    )
    assert wh_logs.exists()
    assert any(log.metadata.get("via") == "stripe_webhook" for log in wh_logs)
