import pytest
from apps.accounts.models import User
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_exam_create_and_get():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    vet = User.objects.create_user(
        username="vet",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )

    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)

    patient = Patient.objects.create(clinic=clinic, owner=owner, name="P", species="dog")

    appt = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=vet,
        starts_at="2025-12-23T10:00:00Z",
        ends_at="2025-12-23T10:30:00Z",
        status="scheduled",
    )

    client = APIClient()
    client.force_authenticate(user=vet)

    payload = {
        "initial_notes": "Initial notes",
        "initial_diagnosis": "Likely otitis externa",
        "temperature_c": "38.5",
        "heart_rate_bpm": 120,
        "respiratory_rate_rpm": 22,
        "owner_instructions": "Give meds with food",
    }

    r_create = client.post(f"/api/appointments/{appt.id}/exam/", payload, format="json")
    assert r_create.status_code == 201
    assert r_create.data["initial_diagnosis"] == "Likely otitis externa"

    r_get = client.get(f"/api/appointments/{appt.id}/exam/")
    assert r_get.status_code == 200
    assert r_get.data["temperature_c"] == "38.5"


@pytest.mark.django_db
def test_exam_all_fields_optional():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    vet = User.objects.create_user(
        username="vet",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )

    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)

    patient = Patient.objects.create(clinic=clinic, owner=owner, name="P", species="dog")

    appt = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=vet,
        starts_at="2025-12-23T10:00:00Z",
        ends_at="2025-12-23T10:30:00Z",
        status="scheduled",
    )

    client = APIClient()
    client.force_authenticate(user=vet)

    # Empty payload should still create (all optional)
    r_create = client.post(f"/api/appointments/{appt.id}/exam/", {}, format="json")
    assert r_create.status_code == 201
