"""Tests for GET /api/patients/<id>/profile/."""

from datetime import timedelta

import pytest
from apps.billing.models import Invoice
from apps.medical.models import MedicalRecord, Vaccination
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def staff_user(clinic):
    """Staff/vet user for profile access."""
    from apps.accounts.models import User

    return User.objects.create_user(
        username="staff",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role="doctor",
    )


@pytest.mark.django_db
def test_profile_returns_200_and_shape(
    clinic,
    staff_user,
    patient,
    doctor,
    client_with_membership,
):
    """Profile returns 200 and all required keys with owner fields."""
    MedicalRecord.objects.create(
        clinic=clinic,
        patient=patient,
        ai_summary="",
    )
    Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Rabies",
        administered_at=timezone.localdate(),
    )
    future = timezone.now() + timedelta(days=1)
    Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=future,
        ends_at=future + timedelta(minutes=30),
        status=Appointment.Status.SCHEDULED,
    )
    Invoice.objects.create(
        clinic=clinic,
        client=patient.owner,
        patient=patient,
        status=Invoice.Status.DRAFT,
    )

    client = APIClient()
    client.force_authenticate(user=staff_user)
    resp = client.get(f"/api/patients/{patient.id}/profile/")

    assert resp.status_code == 200
    data = resp.data
    assert "patient" in data
    assert "owner" in data
    assert "medical_records" in data
    assert "vaccinations" in data
    assert "upcoming_appointments" in data
    assert "open_invoices" in data
    owner = data["owner"]
    assert "id" in owner
    assert "first_name" in owner
    assert "last_name" in owner
    assert "phone" in owner
    assert "email" in owner


@pytest.mark.django_db
def test_profile_medical_records_last_5(clinic, staff_user, patient):
    """Only last 5 medical records returned, newest first."""
    for i in range(7):
        MedicalRecord.objects.create(
            clinic=clinic,
            patient=patient,
            ai_summary=f"Record {i}",
        )

    client = APIClient()
    client.force_authenticate(user=staff_user)
    resp = client.get(f"/api/patients/{patient.id}/profile/")

    assert resp.status_code == 200
    medical_records = resp.data["medical_records"]
    assert len(medical_records) == 5
    created_ats = [r["created_at"] for r in medical_records]
    assert created_ats == sorted(created_ats, reverse=True)


@pytest.mark.django_db
def test_profile_vaccinations_ordered(clinic, staff_user, patient, doctor):
    """Vaccinations ordered by administered_at desc."""
    Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="First",
        administered_at=timezone.localdate() - timedelta(days=10),
        administered_by=doctor,
    )
    Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Second",
        administered_at=timezone.localdate() - timedelta(days=5),
        administered_by=doctor,
    )

    client = APIClient()
    client.force_authenticate(user=staff_user)
    resp = client.get(f"/api/patients/{patient.id}/profile/")

    assert resp.status_code == 200
    vaccinations = resp.data["vaccinations"]
    assert len(vaccinations) == 2
    assert vaccinations[0]["vaccine_name"] == "Second"
    assert vaccinations[1]["vaccine_name"] == "First"


@pytest.mark.django_db
def test_profile_upcoming_appointments_next_3(clinic, staff_user, patient, doctor):
    """Only next 3 upcoming appointments, ordered by starts_at asc."""
    base = timezone.now() + timedelta(days=1)
    for i in range(5):
        start = base.replace(hour=10 + i, minute=0, second=0, microsecond=0)
        Appointment.objects.create(
            clinic=clinic,
            patient=patient,
            vet=doctor,
            starts_at=start,
            ends_at=start + timedelta(minutes=30),
            status=Appointment.Status.SCHEDULED,
        )

    client = APIClient()
    client.force_authenticate(user=staff_user)
    resp = client.get(f"/api/patients/{patient.id}/profile/")

    assert resp.status_code == 200
    upcoming = resp.data["upcoming_appointments"]
    assert len(upcoming) == 3
    starts = [a["starts_at"] for a in upcoming]
    assert starts == sorted(starts)


@pytest.mark.django_db
def test_profile_open_invoices_only(clinic, staff_user, patient, client_with_membership):
    """Open invoices: only draft, sent, overdue (not paid/cancelled)."""
    for status in [
        Invoice.Status.DRAFT,
        Invoice.Status.SENT,
        Invoice.Status.OVERDUE,
        Invoice.Status.PAID,
        Invoice.Status.CANCELLED,
    ]:
        Invoice.objects.create(
            clinic=clinic,
            client=client_with_membership,
            patient=patient,
            status=status,
        )

    client = APIClient()
    client.force_authenticate(user=staff_user)
    resp = client.get(f"/api/patients/{patient.id}/profile/")

    assert resp.status_code == 200
    open_invoices = resp.data["open_invoices"]
    assert len(open_invoices) == 3
    statuses = {inv["status"] for inv in open_invoices}
    assert statuses == {"draft", "sent", "overdue"}


@pytest.mark.django_db
def test_profile_404_other_clinic(staff_user, client_with_membership, doctor):
    """Profile for patient in another clinic returns 404."""
    from apps.patients.models import Patient

    clinic_b = Clinic.objects.create(
        name="Clinic B",
        address="b",
        phone="b",
        email="b@b.com",
    )
    from apps.clients.models import ClientClinic

    ClientClinic.objects.create(
        client=client_with_membership,
        clinic=clinic_b,
        is_active=True,
    )
    patient_b = Patient.objects.create(
        clinic=clinic_b,
        owner=client_with_membership,
        name="Other",
        species="Cat",
    )

    client = APIClient()
    client.force_authenticate(user=staff_user)
    resp = client.get(f"/api/patients/{patient_b.id}/profile/")

    assert resp.status_code == 404


@pytest.mark.django_db
def test_profile_empty_lists(clinic, staff_user, patient):
    """Profile with no records returns 200 and empty arrays."""
    client = APIClient()
    client.force_authenticate(user=staff_user)
    resp = client.get(f"/api/patients/{patient.id}/profile/")

    assert resp.status_code == 200
    assert resp.data["medical_records"] == []
    assert resp.data["vaccinations"] == []
    assert resp.data["upcoming_appointments"] == []
    assert resp.data["open_invoices"] == []
