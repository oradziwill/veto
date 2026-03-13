from datetime import timedelta

import pytest
from apps.accounts.models import User
from apps.clients.models import Client, ClientClinic
from apps.medical.models import Vaccination
from apps.patients.models import Patient
from apps.tenancy.models import Clinic
from django.utils import timezone
from rest_framework.test import APIClient


def _make_clinic_user_patient(clinic_name="C1", username="vet", is_vet=True, is_staff=True):
    clinic = Clinic.objects.create(name=clinic_name, address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username=username,
        password="pass",
        clinic=clinic,
        is_vet=is_vet,
        is_staff=is_staff,
    )
    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)
    patient = Patient.objects.create(clinic=clinic, owner=owner, name="P", species="dog")
    return clinic, user, patient


def _as_list(data):
    return data if isinstance(data, list) else data.get("results", [])


@pytest.mark.django_db
def test_patient_vaccination_list_happy_path():
    clinic, vet, patient = _make_clinic_user_patient()
    Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Rabies",
        administered_at="2025-01-10",
        next_due_at="2026-01-10",
        administered_by=vet,
    )
    Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Parvovirus",
        administered_at="2025-01-15",
        administered_by=vet,
    )

    client = APIClient()
    client.force_authenticate(user=vet)

    resp = client.get(f"/api/patients/{patient.id}/vaccinations/")
    assert resp.status_code == 200
    assert len(resp.data) == 2
    # Newest first (administered_at desc)
    assert resp.data[0]["administered_at"] >= resp.data[1]["administered_at"]
    assert resp.data[0]["vaccine_name"] == "Parvovirus"
    assert resp.data[1]["vaccine_name"] == "Rabies"
    for item in resp.data:
        assert "id" in item
        assert "vaccine_name" in item
        assert "administered_at" in item
        assert "next_due_at" in item
        assert "patient" in item
        assert "clinic" in item


@pytest.mark.django_db
def test_patient_vaccination_list_empty():
    clinic, vet, patient = _make_clinic_user_patient()
    client = APIClient()
    client.force_authenticate(user=vet)

    resp = client.get(f"/api/patients/{patient.id}/vaccinations/")
    assert resp.status_code == 200
    assert resp.data == []


@pytest.mark.django_db
def test_patient_vaccination_create_happy_path():
    clinic, vet, patient = _make_clinic_user_patient()
    client = APIClient()
    client.force_authenticate(user=vet)

    payload = {
        "vaccine_name": "Wścieklizna",
        "administered_at": "2025-02-01",
        "next_due_at": "2026-02-01",
        "notes": "Annual booster",
        "batch_number": "BATCH-001",
    }
    resp = client.post(
        f"/api/patients/{patient.id}/vaccinations/",
        data=payload,
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["vaccine_name"] == "Wścieklizna"
    assert resp.data["administered_at"] == "2025-02-01"
    assert resp.data["next_due_at"] == "2026-02-01"
    assert resp.data["notes"] == "Annual booster"
    assert resp.data["batch_number"] == "BATCH-001"
    assert resp.data["patient"] == patient.id
    assert resp.data["clinic"] == clinic.id
    assert resp.data["administered_by"] == vet.id
    assert "id" in resp.data

    assert Vaccination.objects.filter(patient=patient).count() == 1


@pytest.mark.django_db
def test_patient_vaccination_create_without_next_due():
    clinic, vet, patient = _make_clinic_user_patient()
    client = APIClient()
    client.force_authenticate(user=vet)

    payload = {
        "vaccine_name": "Parwowirus",
        "administered_at": "2025-03-01",
    }
    resp = client.post(
        f"/api/patients/{patient.id}/vaccinations/",
        data=payload,
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["vaccine_name"] == "Parwowirus"
    assert resp.data["administered_at"] == "2025-03-01"
    assert resp.data["next_due_at"] is None


@pytest.mark.django_db
def test_patient_vaccination_list_forbidden_for_non_staff_non_vet():
    clinic, user, patient = _make_clinic_user_patient(username="u", is_vet=False, is_staff=False)
    user.role = ""
    user.save(update_fields=["role"])

    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get(f"/api/patients/{patient.id}/vaccinations/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_patient_vaccination_create_forbidden_for_non_staff_non_vet():
    clinic, user, patient = _make_clinic_user_patient(username="u", is_vet=False, is_staff=False)
    user.role = ""
    user.save(update_fields=["role"])

    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.post(
        f"/api/patients/{patient.id}/vaccinations/",
        data={"vaccine_name": "Rabies", "administered_at": "2025-01-01"},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_vaccination_clinic_isolation_list():
    clinic_a, user_a, patient_a = _make_clinic_user_patient(clinic_name="C1", username="vet_a")
    clinic_b, _, patient_b = _make_clinic_user_patient(clinic_name="C2", username="vet_b")
    Vaccination.objects.create(
        clinic=clinic_a,
        patient=patient_a,
        vaccine_name="Rabies A",
        administered_at="2025-01-01",
        administered_by=user_a,
    )
    Vaccination.objects.create(
        clinic=clinic_b,
        patient=patient_b,
        vaccine_name="Rabies B",
        administered_at="2025-01-02",
    )

    client = APIClient()
    client.force_authenticate(user=user_a)

    resp = client.get(f"/api/patients/{patient_a.id}/vaccinations/")
    assert resp.status_code == 200
    assert len(resp.data) == 1
    assert resp.data[0]["vaccine_name"] == "Rabies A"


@pytest.mark.django_db
def test_vaccination_clinic_isolation_retrieve():
    clinic_a, user_a, patient_a = _make_clinic_user_patient(clinic_name="C1", username="vet_a")
    clinic_b, _, patient_b = _make_clinic_user_patient(clinic_name="C2", username="vet_b")
    vax_b = Vaccination.objects.create(
        clinic=clinic_b,
        patient=patient_b,
        vaccine_name="Rabies B",
        administered_at="2025-01-02",
    )

    client = APIClient()
    client.force_authenticate(user=user_a)

    resp = client.get(f"/api/vaccinations/{vax_b.id}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_vaccination_update_happy_path():
    clinic, vet, patient = _make_clinic_user_patient()
    vax = Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Rabies",
        administered_at="2025-01-01",
        next_due_at="2026-01-01",
        administered_by=vet,
        notes="Initial",
    )

    client = APIClient()
    client.force_authenticate(user=vet)

    resp = client.patch(
        f"/api/vaccinations/{vax.id}/",
        data={"notes": "Updated notes", "next_due_at": "2026-06-01"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["id"] == vax.id
    assert resp.data["clinic"] == clinic.id
    assert resp.data["patient"] == patient.id
    assert resp.data["administered_by"] == vet.id
    assert resp.data["administered_by_name"] == vet.username
    assert resp.data["vaccine_name"] == "Rabies"
    assert resp.data["administered_at"] == "2025-01-01"
    assert resp.data["notes"] == "Updated notes"
    assert resp.data["next_due_at"] == "2026-06-01"

    vax.refresh_from_db()
    assert vax.notes == "Updated notes"
    assert str(vax.next_due_at) == "2026-06-01"


@pytest.mark.django_db
def test_vaccination_delete_happy_path():
    clinic, vet, patient = _make_clinic_user_patient()
    vax = Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Rabies",
        administered_at="2025-01-01",
        administered_by=vet,
    )
    vax_id = vax.id

    client = APIClient()
    client.force_authenticate(user=vet)

    resp = client.delete(f"/api/vaccinations/{vax_id}/")
    assert resp.status_code == 204

    assert not Vaccination.objects.filter(id=vax_id).exists()


@pytest.mark.django_db
def test_vaccination_update_forbidden_other_clinic():
    clinic_a, user_a, patient_a = _make_clinic_user_patient(clinic_name="C1", username="vet_a")
    clinic_b, _, patient_b = _make_clinic_user_patient(clinic_name="C2", username="vet_b")
    vax_b = Vaccination.objects.create(
        clinic=clinic_b,
        patient=patient_b,
        vaccine_name="Rabies B",
        administered_at="2025-01-02",
    )

    client = APIClient()
    client.force_authenticate(user=user_a)

    resp = client.patch(
        f"/api/vaccinations/{vax_b.id}/",
        data={"notes": "Hacked"},
        format="json",
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_vaccination_create_validation_required_fields():
    clinic, vet, patient = _make_clinic_user_patient()
    client = APIClient()
    client.force_authenticate(user=vet)

    # Missing vaccine_name
    resp = client.post(
        f"/api/patients/{patient.id}/vaccinations/",
        data={"administered_at": "2025-01-01"},
        format="json",
    )
    assert resp.status_code == 400
    assert "vaccine_name" in resp.data

    # Missing administered_at
    resp2 = client.post(
        f"/api/patients/{patient.id}/vaccinations/",
        data={"vaccine_name": "Rabies"},
        format="json",
    )
    assert resp2.status_code == 400
    assert "administered_at" in resp2.data


@pytest.mark.django_db
def test_patient_vaccination_list_upcoming_filter():
    clinic, vet, patient = _make_clinic_user_patient()
    today = timezone.now().date()

    Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="No due",
        administered_at="2025-01-01",
        next_due_at=None,
        administered_by=vet,
    )
    Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Past due",
        administered_at="2025-01-02",
        next_due_at=today - timedelta(days=1),
        administered_by=vet,
    )
    today_due = Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Due today",
        administered_at="2025-01-03",
        next_due_at=today,
        administered_by=vet,
    )
    future_due = Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Due later",
        administered_at="2025-01-04",
        next_due_at=today + timedelta(days=30),
        administered_by=vet,
    )

    client = APIClient()
    client.force_authenticate(user=vet)

    resp = client.get(f"/api/patients/{patient.id}/vaccinations/?upcoming=1")
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.data}
    assert ids == {today_due.id, future_due.id}


@pytest.mark.django_db
def test_vaccinations_due_within_days_default_excludes_overdue():
    clinic, vet, patient = _make_clinic_user_patient()
    today = timezone.localdate()

    overdue = Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Overdue",
        administered_at="2025-01-01",
        next_due_at=today - timedelta(days=2),
        administered_by=vet,
    )
    due_soon = Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Soon",
        administered_at="2025-01-02",
        next_due_at=today + timedelta(days=7),
        administered_by=vet,
    )
    Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Later",
        administered_at="2025-01-03",
        next_due_at=today + timedelta(days=40),
        administered_by=vet,
    )

    client = APIClient()
    client.force_authenticate(user=vet)
    resp = client.get("/api/vaccinations/?due_within_days=30")
    assert resp.status_code == 200

    rows = _as_list(resp.data)
    ids = {item["id"] for item in rows}
    assert due_soon.id in ids
    assert overdue.id not in ids


@pytest.mark.django_db
def test_vaccinations_due_within_days_include_overdue_and_response_fields():
    clinic, vet, patient = _make_clinic_user_patient()
    today = timezone.localdate()
    overdue = Vaccination.objects.create(
        clinic=clinic,
        patient=patient,
        vaccine_name="Rabies",
        administered_at="2025-01-01",
        next_due_at=today - timedelta(days=1),
        administered_by=vet,
    )

    client = APIClient()
    client.force_authenticate(user=vet)
    resp = client.get("/api/vaccinations/?due_within_days=30&include_overdue=1")
    assert resp.status_code == 200

    rows = _as_list(resp.data)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == overdue.id
    assert row["vaccine_name"] == "Rabies"
    assert row["next_due_date"] == str(overdue.next_due_at)
    assert row["patient_name"] == patient.name
    assert row["owner_name"] == f"{patient.owner.first_name} {patient.owner.last_name}"


@pytest.mark.django_db
def test_vaccinations_due_within_days_invalid_value_returns_400():
    clinic, vet, patient = _make_clinic_user_patient()
    client = APIClient()
    client.force_authenticate(user=vet)

    resp = client.get("/api/vaccinations/?due_within_days=abc")
    assert resp.status_code == 400
    assert "due_within_days" in resp.data


@pytest.mark.django_db
def test_vaccinations_due_within_days_clinic_scoped():
    clinic_a, user_a, patient_a = _make_clinic_user_patient(clinic_name="C1", username="vet_a")
    clinic_b, _, patient_b = _make_clinic_user_patient(clinic_name="C2", username="vet_b")
    today = timezone.localdate()

    due_a = Vaccination.objects.create(
        clinic=clinic_a,
        patient=patient_a,
        vaccine_name="A due",
        administered_at="2025-01-01",
        next_due_at=today + timedelta(days=5),
        administered_by=user_a,
    )
    due_b = Vaccination.objects.create(
        clinic=clinic_b,
        patient=patient_b,
        vaccine_name="B due",
        administered_at="2025-01-01",
        next_due_at=today + timedelta(days=5),
    )

    client = APIClient()
    client.force_authenticate(user=user_a)
    resp = client.get("/api/vaccinations/?due_within_days=30")
    assert resp.status_code == 200
    ids = {item["id"] for item in _as_list(resp.data)}
    assert due_a.id in ids
    assert due_b.id not in ids
