import pytest
from apps.accounts.models import User
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_prescription_requires_closed_visit():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    vet = User.objects.create_user(
        username="vet", password="pass", clinic=clinic, is_vet=True, is_staff=True
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
        "medication": "Amoxicillin",
        "instructions": "With food",
        "quantity": "10 tabs",
        "refills": 0,
    }
    resp = client.post(f"/api/appointments/{appt.id}/prescriptions/", payload, format="json")
    assert resp.status_code == 400
    assert "Visit must be closed" in resp.data["detail"]


@pytest.mark.django_db
def test_prescription_happy_path_after_close():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    vet = User.objects.create_user(
        username="vet", password="pass", clinic=clinic, is_vet=True, is_staff=True
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

    # create exam first
    r_exam = client.post(
        f"/api/appointments/{appt.id}/exam/", {"initial_notes": "ok"}, format="json"
    )
    assert r_exam.status_code == 201

    # close visit
    r_close = client.post(f"/api/appointments/{appt.id}/close_visit/", {}, format="json")
    assert r_close.status_code in (200, 204)

    payload = {
        "medication": "Amoxicillin",
        "instructions": "With food",
        "quantity": "10 tabs",
        "refills": 0,
    }
    r_rx = client.post(f"/api/appointments/{appt.id}/prescriptions/", payload, format="json")
    assert r_rx.status_code == 201
    assert r_rx.data["medication"] == "Amoxicillin"
    assert r_rx.data["appointment"] == appt.id
    assert r_rx.data["patient"] == patient.id

    # list
    r_list = client.get(f"/api/appointments/{appt.id}/prescriptions/")
    assert r_list.status_code == 200
    assert len(r_list.data) == 1


@pytest.mark.django_db
def test_prescription_forbidden_for_non_vet():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    staff = User.objects.create_user(
        username="staff", password="pass", clinic=clinic, is_vet=False, is_staff=True
    )
    vet = User.objects.create_user(
        username="vet", password="pass", clinic=clinic, is_vet=True, is_staff=True
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
    client.force_authenticate(user=staff)

    payload = {"medication": "Amoxicillin", "instructions": "With food"}
    resp = client.post(f"/api/appointments/{appt.id}/prescriptions/", payload, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_prescription_not_found_outside_clinic():
    clinic1 = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    clinic2 = Clinic.objects.create(name="C2", address="a2", phone="p2", email="e2@e.com")

    vet1 = User.objects.create_user(
        username="vet1", password="pass", clinic=clinic1, is_vet=True, is_staff=True
    )
    vet2 = User.objects.create_user(
        username="vet2", password="pass", clinic=clinic2, is_vet=True, is_staff=True
    )

    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic2)
    patient = Patient.objects.create(clinic=clinic2, owner=owner, name="P", species="dog")

    appt = Appointment.objects.create(
        clinic=clinic2,
        patient=patient,
        vet=vet2,
        starts_at="2025-12-23T10:00:00Z",
        ends_at="2025-12-23T10:30:00Z",
        status="completed",
    )

    client = APIClient()
    client.force_authenticate(user=vet1)

    payload = {"medication": "Amoxicillin", "instructions": "With food"}
    resp = client.post(f"/api/appointments/{appt.id}/prescriptions/", payload, format="json")
    assert resp.status_code == 404
