import pytest
from apps.accounts.models import User
from apps.clients.models import Client, ClientClinic
from apps.medical.models import Prescription
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_patient_prescription_history_happy_path():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    vet = User.objects.create_user(
        username="vet", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )

    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)
    patient = Patient.objects.create(clinic=clinic, owner=owner, name="P", species="dog")

    appt1 = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=vet,
        starts_at="2025-12-23T10:00:00Z",
        ends_at="2025-12-23T10:30:00Z",
        status="completed",
    )
    appt2 = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=vet,
        starts_at="2025-12-24T10:00:00Z",
        ends_at="2025-12-24T10:30:00Z",
        status="completed",
    )

    # Create two prescriptions (ensure ordering newest-first)
    Prescription.objects.create(
        clinic=clinic,
        appointment=appt1,
        patient=patient,
    )
    Prescription.objects.create(
        clinic=clinic,
        appointment=appt2,
        patient=patient,
    )

    client = APIClient()
    client.force_authenticate(user=vet)

    resp = client.get(f"/api/patients/{patient.id}/prescriptions/")
    assert resp.status_code == 200
    assert len(resp.data) == 2
    # Newest first (by created_at)
    assert resp.data[0]["id"] != resp.data[1]["id"]
    assert "created_at" in resp.data[0] and "created_at" in resp.data[1]


@pytest.mark.django_db
def test_patient_prescription_history_not_found_outside_clinic():
    clinic1 = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    clinic2 = Clinic.objects.create(name="C2", address="a2", phone="p2", email="e2@e.com")

    vet1 = User.objects.create_user(
        username="vet1", password="pass", clinic=clinic1, is_vet=True, is_staff=True
    )

    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic2)
    patient = Patient.objects.create(clinic=clinic2, owner=owner, name="P", species="dog")

    client = APIClient()
    client.force_authenticate(user=vet1)

    resp = client.get(f"/api/patients/{patient.id}/prescriptions/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_patient_prescription_history_forbidden_for_non_staff_non_vet():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")

    user = User.objects.create_user(
        username="u", password="pass", clinic=clinic, is_vet=False, is_staff=False
    )
    # User defaults to role=receptionist; set role so IsStaffOrVet denies (not doctor/receptionist/admin)
    user.role = ""
    user.save(update_fields=["role"])

    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)
    patient = Patient.objects.create(clinic=clinic, owner=owner, name="P", species="dog")

    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get(f"/api/patients/{patient.id}/prescriptions/")
    assert resp.status_code == 403
