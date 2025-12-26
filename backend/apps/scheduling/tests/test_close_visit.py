import pytest
from apps.accounts.models import User
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic
from django.urls import reverse
from rest_framework.test import APIClient


def close_visit_url(appt_id: int) -> str:
    return reverse("appointments-close-visit", args=[appt_id])


@pytest.mark.django_db
def test_close_visit_happy_path_by_vet():
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

    resp = client.post(close_visit_url(appt.id), {}, format="json")
    assert resp.status_code in (200, 204)

    appt.refresh_from_db()
    assert appt.status == "completed"


@pytest.mark.django_db
def test_close_visit_forbidden_for_non_vet():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")

    # Authenticated user is staff (non-vet)
    staff = User.objects.create_user(
        username="staff", password="pass", clinic=clinic, is_vet=False, is_staff=True
    )

    # Appointment must reference a valid vet user due to model validation
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

    resp = client.post(close_visit_url(appt.id), {}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_close_visit_not_found_outside_clinic():
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
        status="scheduled",
    )

    client = APIClient()
    client.force_authenticate(user=vet1)

    # get_object() is clinic-scoped -> should be 404
    resp = client.post(close_visit_url(appt.id), {}, format="json")
    assert resp.status_code == 404
