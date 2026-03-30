from datetime import time

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.scheduling.models import Appointment
from apps.scheduling.models_working_hours import VetWorkingHours


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
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_portal_otp_and_booking_happy_path(
    api_client,
    clinic,
    doctor_with_all_weekdays_hours,
    patient,
    client_with_membership,
):
    clinic.refresh_from_db()
    slug = clinic.slug
    today = timezone.localdate().isoformat()

    vets = api_client.get(f"/api/portal/clinics/{slug}/vets/")
    assert vets.status_code == 200
    assert any(v["id"] == doctor_with_all_weekdays_hours.id for v in vets.data)

    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    assert av.status_code == 200
    assert av.data.get("closed_reason") is None
    free = av.data["free"]
    assert len(free) >= 1
    slot = free[0]

    req = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": client_with_membership.email},
        format="json",
    )
    assert req.status_code == 200
    code = req.data["_dev_otp"]

    conf = api_client.post(
        "/api/portal/auth/confirm-code/",
        {
            "clinic_slug": slug,
            "email": client_with_membership.email,
            "code": code,
        },
        format="json",
    )
    assert conf.status_code == 200
    access = conf.data["access"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    pets = api_client.get("/api/portal/me/patients/")
    assert pets.status_code == 200
    assert any(p["id"] == patient.id for p in pets.data)

    book = api_client.post(
        "/api/portal/appointments/",
        {
            "patient_id": patient.id,
            "vet_id": doctor_with_all_weekdays_hours.id,
            "starts_at": slot["start"],
            "ends_at": slot["end"],
            "reason": "Portal booking",
        },
        format="json",
    )
    assert book.status_code == 201
    appt_id = book.data["id"]
    assert book.data["status"] == Appointment.Status.CONFIRMED
    assert book.data["payment_required"] is False

    ev = AuditLog.objects.filter(
        action="portal_appointment_booked",
        entity_id=str(appt_id),
    ).first()
    assert ev is not None

    listed = api_client.get("/api/portal/appointments/")
    assert listed.status_code == 200
    assert any(a["id"] == appt_id for a in listed.data)

    cancel = api_client.post(
        f"/api/portal/appointments/{appt_id}/cancel/",
        {"cancellation_reason": "Plans changed"},
        format="json",
    )
    assert cancel.status_code == 204
    appt = Appointment.objects.get(pk=appt_id)
    assert appt.status == Appointment.Status.CANCELLED


@pytest.mark.django_db
def test_portal_online_booking_disabled_blocks_public_availability(
    api_client,
    clinic,
    doctor_with_all_weekdays_hours,
):
    clinic.online_booking_enabled = False
    clinic.save(update_fields=["online_booking_enabled"])
    clinic.refresh_from_db()
    slug = clinic.slug
    today = timezone.localdate().isoformat()

    av = api_client.get(
        f"/api/portal/clinics/{slug}/availability/",
        {"date": today, "vet": doctor_with_all_weekdays_hours.id},
    )
    assert av.status_code == 403
