from datetime import UTC, datetime

import pytest
from apps.accounts.models import User
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic
from django.urls import reverse
from rest_framework.test import APIClient


def cancellation_analytics_url() -> str:
    return reverse("appointments-cancellation-analytics")


@pytest.mark.django_db
def test_setting_status_to_cancelled_sets_cancelled_at():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    vet = User.objects.create_user(
        username="vet_cancel_set",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )
    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)
    patient = Patient.objects.create(clinic=clinic, owner=owner, name="Rex", species="dog")
    appt = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=vet,
        starts_at="2026-04-01T10:00:00Z",
        ends_at="2026-04-01T10:30:00Z",
        status=Appointment.Status.SCHEDULED,
    )

    client = APIClient()
    client.force_authenticate(user=vet)
    resp = client.patch(
        reverse("appointments-detail", args=[appt.id]),
        {"status": Appointment.Status.CANCELLED},
        format="json",
    )
    assert resp.status_code == 200

    appt.refresh_from_db()
    assert appt.status == Appointment.Status.CANCELLED
    assert appt.cancelled_at is not None


@pytest.mark.django_db
def test_cancellation_analytics_aggregates_expected_groups():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    vet1 = User.objects.create_user(
        username="vet1_analytics",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )
    vet2 = User.objects.create_user(
        username="vet2_analytics",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )
    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)
    patient = Patient.objects.create(clinic=clinic, owner=owner, name="Luna", species="cat")

    Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=vet1,
        starts_at="2026-04-10T10:00:00Z",
        ends_at="2026-04-10T10:30:00Z",
        visit_type=Appointment.VisitType.OUTPATIENT,
        status=Appointment.Status.CANCELLED,
        cancelled_by=Appointment.CancelledBy.CLIENT,
        cancellation_reason="Owner unavailable",
        cancelled_at=datetime(2026, 4, 10, 9, 30, tzinfo=UTC),
    )
    Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=vet1,
        starts_at="2026-04-12T10:00:00Z",
        ends_at="2026-04-12T10:30:00Z",
        visit_type=Appointment.VisitType.HOSPITALIZATION,
        status=Appointment.Status.NO_SHOW,
    )
    Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=vet2,
        starts_at="2026-04-15T10:00:00Z",
        ends_at="2026-04-15T10:30:00Z",
        visit_type=Appointment.VisitType.OUTPATIENT,
        status=Appointment.Status.CANCELLED,
        cancelled_by=Appointment.CancelledBy.CLINIC,
        cancellation_reason="Vet unavailable",
        cancelled_at=datetime(2026, 4, 8, 10, 0, tzinfo=UTC),
    )

    client = APIClient()
    client.force_authenticate(user=vet1)
    resp = client.get(
        cancellation_analytics_url(),
        {"date_from": "2026-04-01", "date_to": "2026-04-30"},
    )

    assert resp.status_code == 200
    assert resp.data["totals"]["cancelled_count"] == 2
    assert resp.data["totals"]["no_show_count"] == 1
    assert resp.data["totals"]["total_count"] == 3
    assert resp.data["cancelled_source"]["client"] == 1
    assert resp.data["cancelled_source"]["clinic"] == 1
    assert resp.data["cancelled_lead_time"]["under_24h"] == 1
    assert resp.data["cancelled_lead_time"]["over_7d"] == 1
    assert len(resp.data["by_vet"]) == 2
    assert len(resp.data["by_visit_type"]) == 2


@pytest.mark.django_db
def test_cancellation_analytics_invalid_date_range_returns_400():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    vet = User.objects.create_user(
        username="vet_bad_dates",
        password="pass",
        clinic=clinic,
        is_vet=True,
        is_staff=True,
        role=User.Role.DOCTOR,
    )

    client = APIClient()
    client.force_authenticate(user=vet)
    resp = client.get(
        cancellation_analytics_url(),
        {"date_from": "2026-05-01", "date_to": "2026-04-01"},
    )
    assert resp.status_code == 400
