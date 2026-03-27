"""Tests for HospitalStay API."""

from datetime import timedelta

import pytest
from apps.scheduling.models import HospitalStay
from django.test import override_settings
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


@pytest.mark.django_db
def test_generate_medication_schedule_is_idempotent(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    starts_at = timezone.now() - timedelta(hours=1)
    order = api_client.post(
        f"/api/hospital-stays/{stay.id}/medications/",
        {
            "medication_name": "Amoxicillin",
            "dose": "25.00",
            "dose_unit": "mg",
            "route": "iv",
            "frequency_hours": 8,
            "starts_at": starts_at.isoformat(),
            "instructions": "",
            "is_active": True,
        },
        format="json",
    )
    assert order.status_code == 201

    first = api_client.post(
        f"/api/hospital-stays/{stay.id}/medications/generate-schedule/?horizon_hours=24&past_hours=2",
        {},
        format="json",
    )
    assert first.status_code == 200
    assert first.data["created"] >= 1

    second = api_client.post(
        f"/api/hospital-stays/{stay.id}/medications/generate-schedule/?horizon_hours=24&past_hours=2",
        {},
        format="json",
    )
    assert second.status_code == 200
    assert second.data["created"] == 0


@pytest.mark.django_db
def test_discharge_summary_returns_draft_when_not_saved(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    response = api_client.get(f"/api/hospital-stays/{stay.id}/discharge-summary/")
    assert response.status_code == 200
    assert response.data["source"] == "draft"
    assert "medications_on_discharge" in response.data


@pytest.mark.django_db
def test_doctor_can_save_and_finalize_discharge_summary(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    save = api_client.put(
        f"/api/hospital-stays/{stay.id}/discharge-summary/",
        {
            "diagnosis": "Post-op recovery",
            "hospitalization_course": "Stable, no complications.",
            "procedures": "Wound care and monitoring",
            "medications_on_discharge": [
                {"medication_name": "Amoxicillin", "dose": "25", "dose_unit": "mg"}
            ],
            "home_care_instructions": "Keep wound dry.",
            "warning_signs": "Fever, lethargy",
            "follow_up_date": "2026-04-10",
        },
        format="json",
    )
    assert save.status_code == 200
    assert save.data["source"] == "saved"
    assert save.data["diagnosis"] == "Post-op recovery"

    finalize_before_discharge = api_client.post(
        f"/api/hospital-stays/{stay.id}/discharge-summary/finalize/",
        {},
        format="json",
    )
    assert finalize_before_discharge.status_code == 400

    discharge = api_client.post(
        f"/api/hospital-stays/{stay.id}/discharge/",
        {"discharge_notes": "Recovered well"},
        format="json",
    )
    assert discharge.status_code == 200

    finalize = api_client.post(
        f"/api/hospital-stays/{stay.id}/discharge-summary/finalize/",
        {},
        format="json",
    )
    assert finalize.status_code == 200
    assert finalize.data["finalized_at"] is not None


@pytest.mark.django_db
def test_discharge_summary_pdf_requires_saved_summary(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    response = api_client.get(f"/api/hospital-stays/{stay.id}/discharge-summary/pdf/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_doctor_can_download_discharge_summary_pdf(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="discharged",
        admitted_at=timezone.now(),
        discharged_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    save = api_client.put(
        f"/api/hospital-stays/{stay.id}/discharge-summary/",
        {
            "diagnosis": "Recovered",
            "hospitalization_course": "No complications.",
            "procedures": "Observation",
            "medications_on_discharge": [
                {"medication_name": "Amoxicillin", "dose": "25", "dose_unit": "mg"}
            ],
            "home_care_instructions": "Limit activity.",
            "warning_signs": "Lethargy",
            "follow_up_date": "2026-04-10",
        },
        format="json",
    )
    assert save.status_code == 200

    response = api_client.get(f"/api/hospital-stays/{stay.id}/discharge-summary/pdf/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].endswith(f'discharge_summary_stay_{stay.id}.pdf"')
    assert response.content.startswith(b"%PDF-1.4")


@pytest.mark.django_db
def test_medications_due_returns_due_items(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    order = api_client.post(
        f"/api/hospital-stays/{stay.id}/medications/",
        {
            "medication_name": "Amoxicillin",
            "dose": "25.00",
            "dose_unit": "mg",
            "route": "iv",
            "frequency_hours": 8,
            "starts_at": (timezone.now() - timedelta(minutes=5)).isoformat(),
            "instructions": "",
            "is_active": True,
        },
        format="json",
    )
    assert order.status_code == 201

    due = api_client.get(f"/api/hospital-stays/{stay.id}/medications-due/?window_minutes=30")
    assert due.status_code == 200
    assert len(due.data["items"]) == 1
    assert due.data["items"][0]["medication_order"]["medication_name"] == "Amoxicillin"
    assert due.data["items"][0]["next_due_at"] is not None


@pytest.mark.django_db
def test_discharge_safety_checks_report_blockers(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    create_task = api_client.post(
        f"/api/hospital-stays/{stay.id}/tasks/",
        {
            "title": "Critical follow-up",
            "priority": "high",
            "status": "pending",
        },
        format="json",
    )
    assert create_task.status_code == 201

    checks = api_client.get(f"/api/hospital-stays/{stay.id}/discharge-safety-checks/")
    assert checks.status_code == 200
    assert checks.data["ready_to_discharge"] is False
    codes = [item["code"] for item in checks.data["blocking_reasons"]]
    assert "discharge_summary_missing" in codes
    assert "high_priority_tasks_open" in codes


@pytest.mark.django_db
def test_discharge_is_blocked_until_safety_requirements_are_met(doctor, patient, api_client):
    stay = HospitalStay.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        attending_vet=doctor,
        status="admitted",
        admitted_at=timezone.now(),
    )
    api_client.force_authenticate(user=doctor)

    with override_settings(REQUIRE_DISCHARGE_SAFETY_FOR_DISCHARGE=True):
        blocked = api_client.post(
            f"/api/hospital-stays/{stay.id}/discharge/",
            {"discharge_notes": "Trying early discharge"},
            format="json",
        )
        assert blocked.status_code == 400
        assert blocked.data["code"] == "discharge_safety_failed"

    save_summary = api_client.put(
        f"/api/hospital-stays/{stay.id}/discharge-summary/",
        {
            "diagnosis": "Recovered",
            "hospitalization_course": "Stable",
            "procedures": "Observation",
            "medications_on_discharge": [],
            "home_care_instructions": "Keep rest for 3 days.",
            "warning_signs": "Fever and vomiting.",
            "follow_up_date": "2026-04-10",
        },
        format="json",
    )
    assert save_summary.status_code == 200

    with override_settings(REQUIRE_DISCHARGE_SAFETY_FOR_DISCHARGE=True):
        allowed = api_client.post(
            f"/api/hospital-stays/{stay.id}/discharge/",
            {"discharge_notes": "Criteria met"},
            format="json",
        )
        assert allowed.status_code == 200
