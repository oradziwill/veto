import pytest
from apps.accounts.models import User
from apps.clients.models import Client, ClientClinic
from apps.medical.models import MedicalRecord
from apps.patients.models import Patient
from apps.tenancy.models import Clinic


@pytest.mark.django_db
def test_medical_record_create_rejects_other_clinic_patient(api_client, doctor):
    clinic_b = Clinic.objects.create(name="C2", address="b", phone="2", email="c2@example.com")
    owner_b = Client.objects.create(first_name="B", last_name="Owner")
    ClientClinic.objects.create(client=owner_b, clinic=clinic_b, is_active=True)
    patient_b = Patient.objects.create(clinic=clinic_b, owner=owner_b, name="P2", species="cat")

    api_client.force_authenticate(user=doctor)
    resp = api_client.post("/api/medical/records/", {"patient": patient_b.id}, format="json")
    assert resp.status_code == 400
    assert resp.data["code"] == "validation_error"
    assert "patient" in resp.data["details"]


@pytest.mark.django_db
def test_medical_history_create_rejects_other_clinic_record(api_client, doctor, patient):
    clinic_b = Clinic.objects.create(name="C2", address="b", phone="2", email="c2@example.com")
    doctor_b = User.objects.create_user(
        username="doctor_b",
        password="pass",
        clinic=clinic_b,
        role=User.Role.DOCTOR,
        is_staff=True,
        is_vet=True,
    )
    owner_b = Client.objects.create(first_name="B", last_name="Owner")
    ClientClinic.objects.create(client=owner_b, clinic=clinic_b, is_active=True)
    patient_b = Patient.objects.create(clinic=clinic_b, owner=owner_b, name="P2", species="cat")
    other_record = MedicalRecord.objects.create(
        clinic=clinic_b,
        patient=patient_b,
        created_by=doctor_b,
    )

    api_client.force_authenticate(user=doctor)
    resp = api_client.post(
        "/api/medical/history/",
        {"record": other_record.id, "note": "Cross clinic should fail"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.data["code"] == "validation_error"
    assert "record" in resp.data["details"]


@pytest.mark.django_db
def test_patient_prescription_create_rejects_record_of_other_patient(api_client, doctor, patient):
    owner2 = Client.objects.create(first_name="Another", last_name="Owner")
    ClientClinic.objects.create(client=owner2, clinic=doctor.clinic, is_active=True)
    patient2 = Patient.objects.create(clinic=doctor.clinic, owner=owner2, name="P2", species="dog")
    record_for_patient2 = MedicalRecord.objects.create(
        clinic=doctor.clinic,
        patient=patient2,
        created_by=doctor,
    )

    api_client.force_authenticate(user=doctor)
    resp = api_client.post(
        f"/api/patients/{patient.id}/prescriptions/",
        {
            "medical_record": record_for_patient2.id,
            "drug_name": "Amoxicillin",
            "dosage": "5mg",
        },
        format="json",
    )
    assert resp.status_code == 400
    assert resp.data["code"] == "validation_error"
    assert "medical_record" in resp.data["details"]


@pytest.mark.django_db
def test_error_response_envelope_for_not_authenticated(api_client):
    resp = api_client.get("/api/patients/")
    assert resp.status_code == 401
    assert resp.data["code"] == "not_authenticated"
    assert "message" in resp.data
    assert "detail" in resp.data
    assert "details" in resp.data
    assert resp.data["status"] == 401
