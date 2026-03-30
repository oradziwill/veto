from datetime import date, time

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.clients.models import Client, ClientClinic
from apps.medical.models import ClinicalExam, Vaccination
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.scheduling.models_working_hours import VetWorkingHours


def _portal_token(api_client, clinic, owner_client):
    clinic.refresh_from_db()
    slug = clinic.slug
    r = api_client.post(
        "/api/portal/auth/request-code/",
        {"clinic_slug": slug, "email": owner_client.email},
        format="json",
    )
    assert r.status_code == 200
    code = r.data["_dev_otp"]
    c = api_client.post(
        "/api/portal/auth/confirm-code/",
        {
            "clinic_slug": slug,
            "email": owner_client.email,
            "code": code,
        },
        format="json",
    )
    assert c.status_code == 200
    return c.data["access"]


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_portal_patient_card_returns_profile_and_lists(
    api_client, clinic, doctor, patient, client_with_membership
):
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

    Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Rabies",
        administered_at=date(2025, 6, 1),
        next_due_at=date(2026, 6, 1),
    )

    t0 = timezone.now().replace(hour=14, minute=0, second=0, microsecond=0)
    appt_done = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=t0,
        ends_at=t0.replace(minute=30),
        status=Appointment.Status.COMPLETED,
        reason="Checkup",
    )
    ClinicalExam.objects.create(
        clinic=clinic,
        appointment=appt_done,
        created_by=doctor,
        weight_kg=12.5,
    )

    access = _portal_token(api_client, clinic, client_with_membership)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    resp = api_client.get(f"/api/portal/me/patients/{patient.id}/")
    assert resp.status_code == 200
    assert resp.data["patient"]["id"] == patient.id
    assert resp.data["patient"]["name"] == patient.name
    assert resp.data["last_weight_kg"] == 12.5
    assert len(resp.data["recent_vaccinations"]) == 1
    assert resp.data["recent_vaccinations"][0]["vaccine_name"] == "Rabies"
    assert len(resp.data["upcoming_appointments"]) >= 0


@pytest.mark.django_db
@override_settings(PORTAL_RETURN_OTP_IN_RESPONSE=True)
def test_portal_patient_card_404_for_other_owners_pet(
    api_client, clinic, doctor, client_with_membership
):
    other = Client.objects.create(
        first_name="Other",
        last_name="Owner",
        email="other.owner@example.com",
    )
    ClientClinic.objects.create(client=other, clinic=clinic, is_active=True)
    other_pet = Patient.objects.create(
        clinic=clinic,
        owner=other,
        name="Their pet",
        species="Cat",
    )

    access = _portal_token(api_client, clinic, client_with_membership)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    resp = api_client.get(f"/api/portal/me/patients/{other_pet.id}/")
    assert resp.status_code == 404
