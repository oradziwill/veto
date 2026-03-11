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
        drug_name="Drug A",
        dosage="5mg 2x daily",
        prescribed_by=vet,
    )
    Prescription.objects.create(
        clinic=clinic,
        appointment=appt2,
        patient=patient,
        drug_name="Drug B",
        dosage="10mg once",
        prescribed_by=vet,
    )

    client = APIClient()
    client.force_authenticate(user=vet)

    resp = client.get(f"/api/patients/{patient.id}/prescriptions/")
    assert resp.status_code == 200
    assert len(resp.data) == 2
    # Newest first (by created_at)
    assert resp.data[0]["id"] != resp.data[1]["id"]
    assert "created_at" in resp.data[0] and "created_at" in resp.data[1]
    assert "drug_name" in resp.data[0] and "dosage" in resp.data[0]


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


@pytest.mark.django_db
def test_patient_prescription_create_happy_path():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    doctor = User.objects.create_user(
        username="doctor",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role="doctor",
    )
    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)
    patient = Patient.objects.create(clinic=clinic, owner=owner, name="P", species="dog")

    client = APIClient()
    client.force_authenticate(user=doctor)

    resp = client.post(
        f"/api/patients/{patient.id}/prescriptions/",
        data={
            "drug_name": "Amoxicillin",
            "dosage": "5mg 2x daily",
            "duration_days": 7,
            "notes": "Take with food",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["drug_name"] == "Amoxicillin"
    assert resp.data["dosage"] == "5mg 2x daily"
    assert resp.data["duration_days"] == 7
    assert resp.data["notes"] == "Take with food"
    assert resp.data["patient"] == patient.id
    assert resp.data["clinic"] == clinic.id
    assert resp.data["prescribed_by"] == doctor.id
    assert Prescription.objects.filter(patient=patient).count() == 1


@pytest.mark.django_db
def test_patient_prescription_create_forbidden_for_receptionist():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    receptionist = User.objects.create_user(
        username="receptionist",
        password="pass",
        clinic=clinic,
        is_vet=False,
        is_staff=False,
        role="receptionist",
    )
    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)
    patient = Patient.objects.create(clinic=clinic, owner=owner, name="P", species="dog")

    client = APIClient()
    client.force_authenticate(user=receptionist)

    resp = client.post(
        f"/api/patients/{patient.id}/prescriptions/",
        data={"drug_name": "Amoxicillin", "dosage": "5mg 2x daily"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_prescription_retrieve_happy_path():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    doctor = User.objects.create_user(
        username="doctor",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role="doctor",
    )
    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)
    patient = Patient.objects.create(clinic=clinic, owner=owner, name="P", species="dog")
    prescription = Prescription.objects.create(
        clinic=clinic,
        patient=patient,
        drug_name="Ibuprofen",
        dosage="200mg as needed",
        prescribed_by=doctor,
    )

    client = APIClient()
    client.force_authenticate(user=doctor)

    resp = client.get(f"/api/prescriptions/{prescription.id}/")
    assert resp.status_code == 200
    assert resp.data["id"] == prescription.id
    assert resp.data["drug_name"] == "Ibuprofen"


@pytest.mark.django_db
def test_prescription_retrieve_404_other_clinic():
    clinic1 = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    clinic2 = Clinic.objects.create(name="C2", address="a2", phone="p2", email="e2@e.com")
    user1 = User.objects.create_user(
        username="u1", password="pass", clinic=clinic1, is_vet=True, is_staff=True
    )
    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic2)
    patient2 = Patient.objects.create(clinic=clinic2, owner=owner, name="P2", species="dog")
    prescription2 = Prescription.objects.create(
        clinic=clinic2,
        patient=patient2,
        drug_name="Drug",
        dosage="1mg",
    )

    client = APIClient()
    client.force_authenticate(user=user1)

    resp = client.get(f"/api/prescriptions/{prescription2.id}/")
    assert resp.status_code == 404
