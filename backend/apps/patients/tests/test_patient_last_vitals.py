from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.medical.models import ClinicalExam
from apps.scheduling.models import Appointment
from django.utils import timezone


@pytest.mark.django_db
def test_patient_last_vitals_returns_204_when_no_exam(api_client, doctor, patient):
    api_client.force_authenticate(user=doctor)
    response = api_client.get(f"/api/patients/{patient.id}/last-vitals/")
    assert response.status_code == 204


@pytest.mark.django_db
def test_patient_last_vitals_returns_latest_exam_values(api_client, doctor, clinic, patient):
    now = timezone.now()
    older_appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now - timedelta(days=2),
        ends_at=now - timedelta(days=2) + timedelta(minutes=30),
        status=Appointment.Status.COMPLETED,
    )
    newer_appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=now - timedelta(days=1),
        ends_at=now - timedelta(days=1) + timedelta(minutes=30),
        status=Appointment.Status.COMPLETED,
    )
    ClinicalExam.objects.create(
        clinic=clinic,
        appointment=older_appointment,
        created_by=doctor,
        temperature_c=Decimal("37.9"),
        heart_rate_bpm=80,
        respiratory_rate_rpm=18,
        weight_kg=Decimal("4.10"),
    )
    newest_exam = ClinicalExam.objects.create(
        clinic=clinic,
        appointment=newer_appointment,
        created_by=doctor,
        temperature_c=Decimal("38.5"),
        heart_rate_bpm=72,
        respiratory_rate_rpm=18,
        weight_kg=Decimal("4.20"),
    )

    api_client.force_authenticate(user=doctor)
    response = api_client.get(f"/api/patients/{patient.id}/last-vitals/")
    assert response.status_code == 200
    assert response.data["temperature_c"] == "38.5"
    assert response.data["heart_rate_bpm"] == 72
    assert response.data["respiratory_rate_rpm"] == 18
    assert response.data["weight_kg"] == "4.20"
    assert response.data["recorded_at"] == newest_exam.created_at.isoformat()
