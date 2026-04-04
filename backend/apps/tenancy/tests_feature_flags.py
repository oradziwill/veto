from datetime import time
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.billing.models import Invoice
from apps.scheduling.models import Appointment
from apps.scheduling.models_working_hours import VetWorkingHours


@pytest.mark.django_db
def test_clinic_features_get_staff(api_client, doctor, clinic):
    api_client.force_authenticate(user=doctor)
    r = api_client.get("/api/clinic-features/")
    assert r.status_code == 200
    assert r.data["feature_ai_enabled"] is True
    assert r.data["feature_ksef_enabled"] is True
    assert r.data["feature_portal_deposit_enabled"] is True


@pytest.mark.django_db
def test_clinic_features_patch_admin(api_client, clinic_admin, clinic):
    api_client.force_authenticate(user=clinic_admin)
    r = api_client.patch(
        "/api/clinic-features/",
        {"feature_ai_enabled": False},
        format="json",
    )
    assert r.status_code == 200
    assert r.data["feature_ai_enabled"] is False
    clinic.refresh_from_db()
    assert clinic.feature_ai_enabled is False


@pytest.mark.django_db
def test_clinic_features_patch_forbidden_for_receptionist(api_client, receptionist, clinic):
    api_client.force_authenticate(user=receptionist)
    r = api_client.patch(
        "/api/clinic-features/",
        {"feature_ai_enabled": False},
        format="json",
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_ai_summary_forbidden_when_feature_off(api_client, doctor, patient, clinic):
    clinic.feature_ai_enabled = False
    clinic.save(update_fields=["feature_ai_enabled"])
    api_client.force_authenticate(user=doctor)
    r = api_client.get(f"/api/patients/{patient.id}/ai-summary/")
    assert r.status_code == 403


@pytest.mark.django_db
def test_ksef_submit_forbidden_when_feature_off(
    api_client, doctor, patient, client_with_membership, clinic
):
    clinic.feature_ksef_enabled = False
    clinic.save(update_fields=["feature_ksef_enabled"])
    inv = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        status=Invoice.Status.DRAFT,
        currency="PLN",
        created_by=doctor,
    )
    api_client.force_authenticate(user=doctor)
    r = api_client.post(f"/api/billing/invoices/{inv.id}/submit-ksef/")
    assert r.status_code == 403


@pytest.mark.django_db
def test_scheduling_assistant_forbidden_when_feature_off(api_client, doctor, clinic):
    clinic.feature_ai_enabled = False
    clinic.save(update_fields=["feature_ai_enabled"])
    api_client.force_authenticate(user=doctor)
    r = api_client.get("/api/schedule/capacity-insights/")
    assert r.status_code == 403


@pytest.mark.django_db
def test_public_clinic_deposit_zero_when_portal_deposit_feature_off(api_client, clinic):
    clinic.portal_booking_deposit_amount = Decimal("50.00")
    clinic.feature_portal_deposit_enabled = False
    clinic.save(update_fields=["portal_booking_deposit_amount", "feature_portal_deposit_enabled"])
    r = api_client.get(f"/api/portal/clinics/{clinic.slug}/")
    assert r.status_code == 200
    assert r.data["portal_booking_deposit_pln"] == "0"


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
def test_portal_booking_skips_deposit_when_feature_off(
    api_client,
    clinic,
    doctor_with_all_weekdays_hours,
    patient,
    client_with_membership,
):
    from django.utils import timezone

    clinic.portal_booking_deposit_amount = Decimal("50.00")
    clinic.feature_portal_deposit_enabled = False
    clinic.save(update_fields=["portal_booking_deposit_amount", "feature_portal_deposit_enabled"])

    slug = clinic.slug
    today = timezone.localdate().isoformat()
    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    assert av.status_code == 200
    slot = av.data["free"][0]

    otp = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": client_with_membership.email},
        format="json",
    )
    assert otp.status_code == 200
    code = otp.data["_dev_otp"]
    auth = api_client.post(
        "/api/portal/auth/confirm-code/",
        {"clinic_slug": slug, "email": client_with_membership.email, "code": code},
        format="json",
    )
    assert auth.status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth.data['access']}")

    book = api_client.post(
        "/api/portal/appointments/",
        {
            "patient_id": patient.id,
            "vet_id": doctor_with_all_weekdays_hours.id,
            "starts_at": slot["start"],
            "ends_at": slot["end"],
            "reason": "No deposit",
        },
        format="json",
    )
    assert book.status_code == 201
    assert book.data["status"] == Appointment.Status.CONFIRMED
    assert book.data["payment_required"] is False
    assert book.data["deposit_invoice_id"] is None
