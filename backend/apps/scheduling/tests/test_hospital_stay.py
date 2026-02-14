"""Tests for HospitalStay API."""

import pytest
from apps.scheduling.models import HospitalStay
from django.utils import timezone


@pytest.mark.django_db
def test_doctor_can_create_hospital_stay(
    doctor,
    patient,
    appointment,
    api_client,
):
    """Doctor can create a hospital stay."""
    api_client.force_authenticate(user=doctor)
    admitted_at = timezone.now()

    r = api_client.post(
        "/api/hospital-stays/",
        {
            "patient": patient.id,
            "attending_vet": doctor.id,
            "admission_appointment": appointment.id,
            "reason": "Surgery recovery",
            "cage_or_room": "Cage 3",
            "admitted_at": admitted_at.isoformat(),
        },
        format="json",
    )
    assert r.status_code == 201
    assert r.data["status"] == "admitted"
    assert r.data["reason"] == "Surgery recovery"
    assert r.data["cage_or_room"] == "Cage 3"


@pytest.mark.django_db
def test_doctor_can_discharge_hospital_stay(
    doctor,
    patient,
    api_client,
):
    """Doctor can discharge a patient."""
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    r = api_client.post(
        f"/api/hospital-stays/{stay.id}/discharge/",
        {"discharge_notes": "Recovered well"},
        format="json",
    )
    assert r.status_code == 200
    stay.refresh_from_db()
    assert stay.status == "discharged"
    assert stay.discharged_at is not None
    assert stay.discharge_notes == "Recovered well"


@pytest.mark.django_db
def test_receptionist_cannot_create_hospital_stay(
    receptionist,
    patient,
    doctor,
    api_client,
):
    """Receptionist cannot create hospital stay."""
    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        "/api/hospital-stays/",
        {
            "patient": patient.id,
            "attending_vet": doctor.id,
            "admitted_at": timezone.now().isoformat(),
        },
        format="json",
    )
    assert r.status_code == 403
