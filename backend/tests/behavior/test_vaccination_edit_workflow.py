"""
Behavior: Vaccination records can be edited consistently for frontend usage.
"""

from datetime import timedelta

import pytest
from apps.medical.models import Vaccination
from django.utils import timezone


@pytest.mark.django_db
class TestVaccinationEditWorkflow:
    def test_patch_vaccination_returns_full_read_record(self, doctor, patient, api_client):
        """PATCH returns full read payload (not write-only fields)."""
        vaccination = Vaccination.objects.create(
            clinic=doctor.clinic,
            patient=patient,
            vaccine_name="Rabies",
            batch_number="RB-1",
            administered_at="2025-01-10",
            next_due_at="2026-01-10",
            administered_by=doctor,
            notes="Initial",
        )

        api_client.force_authenticate(user=doctor)
        resp = api_client.patch(
            f"/api/vaccinations/{vaccination.id}/",
            {"notes": "Updated by patch"},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.data["id"] == vaccination.id
        assert resp.data["clinic"] == doctor.clinic_id
        assert resp.data["patient"] == patient.id
        assert resp.data["administered_by"] == doctor.id
        assert resp.data["administered_by_name"] == doctor.username
        assert resp.data["vaccine_name"] == "Rabies"
        assert resp.data["notes"] == "Updated by patch"

    def test_delete_vaccination_removes_record(self, doctor, patient, api_client):
        """DELETE removes the vaccination record."""
        vaccination = Vaccination.objects.create(
            clinic=doctor.clinic,
            patient=patient,
            vaccine_name="Parvovirus",
            administered_at="2025-01-10",
            administered_by=doctor,
        )

        api_client.force_authenticate(user=doctor)
        resp = api_client.delete(f"/api/vaccinations/{vaccination.id}/")

        assert resp.status_code == 204
        assert not Vaccination.objects.filter(pk=vaccination.id).exists()

    def test_upcoming_filter_returns_only_due_today_or_future(self, doctor, patient, api_client):
        """?upcoming=1 keeps next_due_at >= today and excludes null/past."""
        today = timezone.localdate()
        past = today - timedelta(days=1)
        future = today + timedelta(days=30)

        past_due = Vaccination.objects.create(
            clinic=doctor.clinic,
            patient=patient,
            vaccine_name="Past due",
            administered_at="2025-01-01",
            next_due_at=past,
            administered_by=doctor,
        )
        no_due = Vaccination.objects.create(
            clinic=doctor.clinic,
            patient=patient,
            vaccine_name="No due date",
            administered_at="2025-01-02",
            next_due_at=None,
            administered_by=doctor,
        )
        due_today = Vaccination.objects.create(
            clinic=doctor.clinic,
            patient=patient,
            vaccine_name="Due today",
            administered_at="2025-01-03",
            next_due_at=today,
            administered_by=doctor,
        )
        due_future = Vaccination.objects.create(
            clinic=doctor.clinic,
            patient=patient,
            vaccine_name="Due future",
            administered_at="2025-01-04",
            next_due_at=future,
            administered_by=doctor,
        )

        api_client.force_authenticate(user=doctor)
        resp = api_client.get(f"/api/patients/{patient.id}/vaccinations/?upcoming=1")
        assert resp.status_code == 200

        ids = {item["id"] for item in resp.data}
        assert due_today.id in ids
        assert due_future.id in ids
        assert past_due.id not in ids
        assert no_due.id not in ids

    def test_due_within_days_filter_with_overdue_toggle(self, doctor, patient, api_client):
        """Behavior: /api/vaccinations/ reminders include readable fields and overdue toggle."""
        today = timezone.localdate()
        overdue = Vaccination.objects.create(
            clinic=doctor.clinic,
            patient=patient,
            vaccine_name="Overdue",
            administered_at="2025-01-01",
            next_due_at=today - timedelta(days=1),
            administered_by=doctor,
        )
        due_soon = Vaccination.objects.create(
            clinic=doctor.clinic,
            patient=patient,
            vaccine_name="Soon",
            administered_at="2025-01-02",
            next_due_at=today + timedelta(days=10),
            administered_by=doctor,
        )
        Vaccination.objects.create(
            clinic=doctor.clinic,
            patient=patient,
            vaccine_name="Later",
            administered_at="2025-01-03",
            next_due_at=today + timedelta(days=45),
            administered_by=doctor,
        )

        api_client.force_authenticate(user=doctor)
        resp = api_client.get("/api/vaccinations/?due_within_days=30")
        assert resp.status_code == 200
        ids = {item["id"] for item in resp.data}
        assert due_soon.id in ids
        assert overdue.id not in ids

        row = next(item for item in resp.data if item["id"] == due_soon.id)
        assert row["patient_name"] == patient.name
        assert row["owner_name"] == f"{patient.owner.first_name} {patient.owner.last_name}"
        assert row["next_due_date"] == str(due_soon.next_due_at)

        resp_with_overdue = api_client.get(
            "/api/vaccinations/?due_within_days=30&include_overdue=1"
        )
        assert resp_with_overdue.status_code == 200
        ids_with_overdue = {item["id"] for item in resp_with_overdue.data}
        assert due_soon.id in ids_with_overdue
        assert overdue.id in ids_with_overdue
