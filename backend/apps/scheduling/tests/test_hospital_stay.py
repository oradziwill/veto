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


@pytest.mark.django_db
def test_doctor_can_manage_hospital_stay_notes(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    create = api_client.post(
        f"/api/hospital-stays/{stay.id}/notes/",
        {"note_type": "round", "note": "Patient stable", "vitals": {"temp_c": 38.7}},
        format="json",
    )
    assert create.status_code == 201
    note_id = create.data["id"]

    listing = api_client.get(f"/api/hospital-stays/{stay.id}/notes/")
    assert listing.status_code == 200
    assert len(listing.data) == 1
    assert listing.data[0]["id"] == note_id

    update = api_client.patch(
        f"/api/hospital-stays/{stay.id}/notes/{note_id}/",
        {"note": "Patient stable, appetite improved"},
        format="json",
    )
    assert update.status_code == 200
    assert "appetite improved" in update.data["note"]


@pytest.mark.django_db
def test_doctor_can_manage_hospital_stay_tasks(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    create = api_client.post(
        f"/api/hospital-stays/{stay.id}/tasks/",
        {
            "title": "Administer antibiotic",
            "description": "Give IV every 8h",
            "priority": "high",
            "status": "pending",
        },
        format="json",
    )
    assert create.status_code == 201
    task_id = create.data["id"]
    assert create.data["completed_at"] is None

    complete = api_client.patch(
        f"/api/hospital-stays/{stay.id}/tasks/{task_id}/",
        {"status": "completed"},
        format="json",
    )
    assert complete.status_code == 200
    assert complete.data["status"] == "completed"
    assert complete.data["completed_at"] is not None

    listing = api_client.get(f"/api/hospital-stays/{stay.id}/tasks/")
    assert listing.status_code == 200
    assert len(listing.data) == 1


@pytest.mark.django_db
def test_doctor_can_manage_hospital_medication_orders(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    create = api_client.post(
        f"/api/hospital-stays/{stay.id}/medications/",
        {
            "medication_name": "Amoxicillin",
            "dose": "25.00",
            "dose_unit": "mg",
            "route": "iv",
            "frequency_hours": 8,
            "starts_at": timezone.now().isoformat(),
            "instructions": "Post-op protocol",
            "is_active": True,
        },
        format="json",
    )
    assert create.status_code == 201
    med_id = create.data["id"]

    listing = api_client.get(f"/api/hospital-stays/{stay.id}/medications/")
    assert listing.status_code == 200
    assert len(listing.data) == 1
    assert listing.data[0]["id"] == med_id

    patch = api_client.patch(
        f"/api/hospital-stays/{stay.id}/medications/{med_id}/",
        {"is_active": False},
        format="json",
    )
    assert patch.status_code == 200
    assert patch.data["is_active"] is False


@pytest.mark.django_db
def test_doctor_can_record_medication_administration(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    med = api_client.post(
        f"/api/hospital-stays/{stay.id}/medications/",
        {
            "medication_name": "Metronidazole",
            "dose": "15.00",
            "dose_unit": "mg",
            "route": "oral",
            "frequency_hours": 12,
            "starts_at": timezone.now().isoformat(),
            "instructions": "",
            "is_active": True,
        },
        format="json",
    )
    assert med.status_code == 201
    med_id = med.data["id"]

    create_admin = api_client.post(
        f"/api/hospital-stays/{stay.id}/medications/{med_id}/administrations/",
        {"status": "given", "note": "Given with food"},
        format="json",
    )
    assert create_admin.status_code == 201
    admin_id = create_admin.data["id"]
    assert create_admin.data["administered_at"] is not None
    assert create_admin.data["administered_by"] == doctor.id

    patch_admin = api_client.patch(
        f"/api/hospital-stays/{stay.id}/medications/{med_id}/administrations/{admin_id}/",
        {"status": "skipped", "note": "Vomited before dose"},
        format="json",
    )
    assert patch_admin.status_code == 200
    assert patch_admin.data["status"] == "skipped"
    assert patch_admin.data["administered_at"] is None
