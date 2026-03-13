import pytest
from apps.medical.models import MedicalRecord, Prescription


@pytest.mark.django_db
def test_prescriptions_list_filter_by_patient(api_client, doctor, patient):
    other_record = MedicalRecord.objects.create(clinic=doctor.clinic, patient=patient)
    p1 = Prescription.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        medical_record=other_record,
        prescribed_by=doctor,
        drug_name="Drug A",
        dosage="1x",
    )
    other_patient = patient.__class__.objects.create(
        clinic=doctor.clinic,
        owner=patient.owner,
        name="Other",
        species=patient.species,
    )
    p2 = Prescription.objects.create(
        clinic=doctor.clinic,
        patient=other_patient,
        prescribed_by=doctor,
        drug_name="Drug B",
        dosage="2x",
    )

    api_client.force_authenticate(user=doctor)
    resp = api_client.get(f"/api/prescriptions/?patient={patient.id}")
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.data}
    assert p1.id in ids
    assert p2.id not in ids


@pytest.mark.django_db
def test_prescriptions_list_filter_by_medical_record(api_client, doctor, patient):
    record_a = MedicalRecord.objects.create(clinic=doctor.clinic, patient=patient)
    record_b = MedicalRecord.objects.create(clinic=doctor.clinic, patient=patient)
    p1 = Prescription.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        medical_record=record_a,
        prescribed_by=doctor,
        drug_name="Drug A",
        dosage="1x",
    )
    p2 = Prescription.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        medical_record=record_b,
        prescribed_by=doctor,
        drug_name="Drug B",
        dosage="2x",
    )

    api_client.force_authenticate(user=doctor)
    resp = api_client.get(f"/api/prescriptions/?medical_record={record_a.id}")
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.data}
    assert p1.id in ids
    assert p2.id not in ids


@pytest.mark.django_db
def test_prescriptions_list_filter_by_patient_and_medical_record(api_client, doctor, patient):
    record_match = MedicalRecord.objects.create(clinic=doctor.clinic, patient=patient)
    record_other = MedicalRecord.objects.create(clinic=doctor.clinic, patient=patient)
    match = Prescription.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        medical_record=record_match,
        prescribed_by=doctor,
        drug_name="Drug A",
        dosage="1x",
    )
    Prescription.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        medical_record=record_other,
        prescribed_by=doctor,
        drug_name="Drug B",
        dosage="2x",
    )

    api_client.force_authenticate(user=doctor)
    resp = api_client.get(
        f"/api/prescriptions/?patient={patient.id}&medical_record={record_match.id}"
    )
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.data}
    assert ids == {match.id}


@pytest.mark.django_db
def test_prescriptions_list_filter_clinic_scoped(api_client, doctor, patient):
    record = MedicalRecord.objects.create(clinic=doctor.clinic, patient=patient)
    in_clinic = Prescription.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        medical_record=record,
        prescribed_by=doctor,
        drug_name="Drug A",
        dosage="1x",
    )

    from apps.accounts.models import User
    from apps.clients.models import Client, ClientClinic
    from apps.tenancy.models import Clinic

    clinic_b = Clinic.objects.create(name="C2", address="b", phone="q", email="e2@e.com")
    doctor_b = User.objects.create_user(
        username="doctor_b",
        password="pass",
        clinic=clinic_b,
        role=User.Role.DOCTOR,
        is_vet=True,
        is_staff=True,
    )
    owner_b = Client.objects.create(first_name="B", last_name="Owner")
    ClientClinic.objects.create(client=owner_b, clinic=clinic_b)
    patient_b = patient.__class__.objects.create(
        clinic=clinic_b,
        owner=owner_b,
        name="P2",
        species="dog",
    )
    record_b = MedicalRecord.objects.create(clinic=clinic_b, patient=patient_b)
    out_clinic = Prescription.objects.create(
        clinic=clinic_b,
        patient=patient_b,
        medical_record=record_b,
        prescribed_by=doctor_b,
        drug_name="Drug B",
        dosage="2x",
    )

    api_client.force_authenticate(user=doctor)
    resp = api_client.get(
        f"/api/prescriptions/?patient={patient_b.id}&medical_record={record_b.id}"
    )
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.data}
    assert in_clinic.id not in ids
    assert out_clinic.id not in ids


@pytest.mark.django_db
def test_prescriptions_list_includes_prescribed_by_name(api_client, doctor, patient):
    record = MedicalRecord.objects.create(clinic=doctor.clinic, patient=patient)
    prescription = Prescription.objects.create(
        clinic=doctor.clinic,
        patient=patient,
        medical_record=record,
        prescribed_by=doctor,
        drug_name="Drug A",
        dosage="1x",
    )

    api_client.force_authenticate(user=doctor)
    list_resp = api_client.get("/api/prescriptions/")
    assert list_resp.status_code == 200
    row = next(item for item in list_resp.data if item["id"] == prescription.id)
    assert row["prescribed_by"] == doctor.id
    assert row["prescribed_by_name"] == doctor.username

    retrieve_resp = api_client.get(f"/api/prescriptions/{prescription.id}/")
    assert retrieve_resp.status_code == 200
    assert retrieve_resp.data["prescribed_by"] == doctor.id
    assert retrieve_resp.data["prescribed_by_name"] == doctor.username
