from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from apps.accounts.models import User
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.scheduling.models_working_hours import VetWorkingHours
from apps.tenancy.models import Clinic
from django.utils import timezone


def _aware(dt: datetime):
    return timezone.make_aware(dt, timezone.get_current_timezone())


@pytest.mark.django_db
def test_schedule_capacity_insights_requires_authentication(api_client):
    response = api_client.get("/api/schedule/capacity-insights/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_schedule_capacity_insights_clinic_scoped_and_calculates_utilization(
    api_client, doctor, clinic, patient
):
    target_day = timezone.localdate() + timedelta(days=1)
    VetWorkingHours.objects.create(
        vet=doctor,
        weekday=target_day.weekday(),
        start_time=datetime.strptime("09:00", "%H:%M").time(),
        end_time=datetime.strptime("17:00", "%H:%M").time(),
        is_active=True,
    )
    Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=_aware(datetime.combine(target_day, datetime.strptime("10:00", "%H:%M").time())),
        ends_at=_aware(datetime.combine(target_day, datetime.strptime("11:00", "%H:%M").time())),
        status=Appointment.Status.SCHEDULED,
    )

    other_clinic = Clinic.objects.create(
        name="Other Clinic",
        address="Street 2",
        phone="+48900000000",
        email="other@example.com",
    )
    other_doctor = User.objects.create_user(
        username="other_doctor_schedule",
        password="pass",
        clinic=other_clinic,
        is_vet=True,
        role=User.Role.DOCTOR,
    )
    other_owner = Client.objects.create(
        first_name="Other",
        last_name="Owner",
        email="owner.other@example.com",
    )
    ClientClinic.objects.create(client=other_owner, clinic=other_clinic, is_active=True)
    other_patient = Patient.objects.create(
        clinic=other_clinic,
        owner=other_owner,
        name="OtherPet",
        species="Dog",
        primary_vet=other_doctor,
    )
    VetWorkingHours.objects.create(
        vet=other_doctor,
        weekday=target_day.weekday(),
        start_time=datetime.strptime("09:00", "%H:%M").time(),
        end_time=datetime.strptime("17:00", "%H:%M").time(),
        is_active=True,
    )
    Appointment.objects.create(
        clinic=other_clinic,
        patient=other_patient,
        vet=other_doctor,
        starts_at=_aware(datetime.combine(target_day, datetime.strptime("10:00", "%H:%M").time())),
        ends_at=_aware(datetime.combine(target_day, datetime.strptime("14:00", "%H:%M").time())),
        status=Appointment.Status.SCHEDULED,
    )

    api_client.force_authenticate(user=doctor)
    response = api_client.get(
        "/api/schedule/capacity-insights/",
        {"from": target_day.isoformat(), "to": target_day.isoformat(), "granularity": "day"},
    )
    assert response.status_code == 200
    assert response.data["kind"] == "scheduling_capacity_insights"
    assert len(response.data["by_vet"]) == 1
    row = response.data["by_vet"][0]
    assert row["vet_id"] == doctor.id
    assert row["available_minutes"] == 480
    assert row["booked_minutes"] == 60
    assert row["utilization_pct"] == 12.5


@pytest.mark.django_db
def test_schedule_optimization_suggestions_returns_reassign(api_client, clinic, doctor, patient):
    target_day = timezone.localdate() + timedelta(days=2)
    backup_vet = User.objects.create_user(
        username="backup_vet_schedule",
        password="pass",
        clinic=clinic,
        is_vet=True,
        role=User.Role.DOCTOR,
    )
    for vet in (doctor, backup_vet):
        VetWorkingHours.objects.create(
            vet=vet,
            weekday=target_day.weekday(),
            start_time=datetime.strptime("09:00", "%H:%M").time(),
            end_time=datetime.strptime("17:00", "%H:%M").time(),
            is_active=True,
        )

    Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=_aware(datetime.combine(target_day, datetime.strptime("10:00", "%H:%M").time())),
        ends_at=_aware(datetime.combine(target_day, datetime.strptime("11:00", "%H:%M").time())),
        status=Appointment.Status.SCHEDULED,
        reason="Checkup",
    )

    api_client.force_authenticate(user=doctor)
    response = api_client.get(
        "/api/schedule/optimization-suggestions/",
        {
            "from": target_day.isoformat(),
            "to": target_day.isoformat(),
            "limit": 5,
            "overload_threshold_pct": 10,
        },
    )
    assert response.status_code == 200
    assert response.data["kind"] == "scheduling_optimization_suggestions"
    assert response.data["count"] >= 1
    first = response.data["suggestions"][0]
    assert first["kind"] in {"reassign_vet", "move_slot"}
    assert "impact_estimate" in first
    assert "reason" in first


@pytest.mark.django_db
def test_schedule_capacity_insights_rejects_invalid_window(api_client, doctor):
    api_client.force_authenticate(user=doctor)
    response = api_client.get(
        "/api/schedule/capacity-insights/",
        {"from": "2026-03-10", "to": "invalid"},
    )
    assert response.status_code == 400
