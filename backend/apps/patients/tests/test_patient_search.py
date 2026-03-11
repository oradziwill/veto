"""Tests for GET /api/patients/?search= (full-text search)."""

import pytest
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from rest_framework.test import APIClient


def _patient_list(resp):
    """Support both list and paginated response."""
    data = resp.data
    return data if isinstance(data, list) else data.get("results", [])


@pytest.mark.django_db
def test_search_by_owner_last_name(clinic, receptionist, doctor):
    """Search by owner last name returns matching patient."""
    client_kowalski = Client.objects.create(
        first_name="Anna",
        last_name="Kowalski",
        phone="+48111222333",
        email="anna.kowalski@test.com",
    )
    ClientClinic.objects.create(client=client_kowalski, clinic=clinic, is_active=True)
    patient = Patient.objects.create(
        clinic=clinic,
        owner=client_kowalski,
        name="Rex",
        species="Dog",
        primary_vet=doctor,
    )

    api = APIClient()
    api.force_authenticate(user=receptionist)
    resp = api.get("/api/patients/", {"search": "kowalski"})

    assert resp.status_code == 200
    ids = [p["id"] for p in _patient_list(resp)]
    assert patient.id in ids


@pytest.mark.django_db
def test_search_by_owner_first_name(clinic, receptionist, doctor):
    """Search by owner first name returns matching patient."""
    client_jan = Client.objects.create(
        first_name="Jan",
        last_name="Nowak",
        phone="+48444555666",
        email="jan.nowak@test.com",
    )
    ClientClinic.objects.create(client=client_jan, clinic=clinic, is_active=True)
    patient = Patient.objects.create(
        clinic=clinic,
        owner=client_jan,
        name="Luna",
        species="Cat",
        primary_vet=doctor,
    )

    api = APIClient()
    api.force_authenticate(user=receptionist)
    resp = api.get("/api/patients/", {"search": "Jan"})

    assert resp.status_code == 200
    ids = [p["id"] for p in _patient_list(resp)]
    assert patient.id in ids


@pytest.mark.django_db
def test_search_by_owner_phone(clinic, receptionist, doctor):
    """Search by owner phone returns matching patient."""
    client_phone = Client.objects.create(
        first_name="Ewa",
        last_name="Wisniewska",
        phone="+48500100200",
        email="ewa.w@test.com",
    )
    ClientClinic.objects.create(client=client_phone, clinic=clinic, is_active=True)
    patient = Patient.objects.create(
        clinic=clinic,
        owner=client_phone,
        name="Pimpek",
        species="Dog",
        primary_vet=doctor,
    )

    api = APIClient()
    api.force_authenticate(user=receptionist)
    resp = api.get("/api/patients/", {"search": "500100"})

    assert resp.status_code == 200
    ids = [p["id"] for p in _patient_list(resp)]
    assert patient.id in ids


@pytest.mark.django_db
def test_search_by_patient_name(clinic, receptionist, doctor, client_with_membership):
    """Search by patient name returns matching patient."""
    patient = Patient.objects.create(
        clinic=clinic,
        owner=client_with_membership,
        name="Burek",
        species="Dog",
        primary_vet=doctor,
    )

    api = APIClient()
    api.force_authenticate(user=receptionist)
    resp = api.get("/api/patients/", {"search": "Burek"})

    assert resp.status_code == 200
    ids = [p["id"] for p in _patient_list(resp)]
    assert patient.id in ids


@pytest.mark.django_db
def test_search_by_microchip_no(clinic, receptionist, doctor, client_with_membership):
    """Search by microchip number returns matching patient."""
    patient = Patient.objects.create(
        clinic=clinic,
        owner=client_with_membership,
        name="Chip",
        species="Dog",
        microchip_no="123456789012345",
        primary_vet=doctor,
    )

    api = APIClient()
    api.force_authenticate(user=receptionist)
    resp = api.get("/api/patients/", {"search": "123456"})

    assert resp.status_code == 200
    ids = [p["id"] for p in _patient_list(resp)]
    assert patient.id in ids


@pytest.mark.django_db
def test_search_case_insensitive(clinic, receptionist, doctor):
    """Search is case-insensitive."""
    client = Client.objects.create(
        first_name="Maria",
        last_name="Kowalski",
        phone="+48777888999",
        email="maria.k@test.com",
    )
    ClientClinic.objects.create(client=client, clinic=clinic, is_active=True)
    patient = Patient.objects.create(
        clinic=clinic,
        owner=client,
        name="Azor",
        species="Dog",
        primary_vet=doctor,
    )

    api = APIClient()
    api.force_authenticate(user=receptionist)

    resp_lower = api.get("/api/patients/", {"search": "kowalski"})
    resp_upper = api.get("/api/patients/", {"search": "KOWALSKI"})

    assert resp_lower.status_code == 200
    assert resp_upper.status_code == 200
    ids_lower = [p["id"] for p in _patient_list(resp_lower)]
    ids_upper = [p["id"] for p in _patient_list(resp_upper)]
    assert patient.id in ids_lower
    assert patient.id in ids_upper
