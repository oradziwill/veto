"""
Behavior: Role-based access control.

As a receptionist, I can book appointments and create invoices but NOT perform
clinical exams or close visits.
As a doctor, I can do clinical exams and close visits.
As clinic admin, I can do everything a doctor can.
"""

import pytest
from django.utils import timezone

from apps.scheduling.models import Appointment


@pytest.mark.django_db
class TestRoleAccess:
    """Verify role-based permissions across modules."""

    def test_receptionist_can_book_appointment_but_not_close_visit(
        self,
        receptionist,
        doctor,
        patient,
        api_client,
    ):
        """Behavior: Receptionist books appointment; only doctor can close visit."""
        api_client.force_authenticate(user=receptionist)

        today = timezone.now()
        starts = today.replace(hour=10, minute=0, second=0, microsecond=0)
        ends = today.replace(hour=10, minute=30, second=0, microsecond=0)

        # Receptionist can create appointment
        r = api_client.post(
            "/api/appointments/",
            {
                "patient": patient.id,
                "vet": doctor.id,
                "starts_at": starts.isoformat(),
                "ends_at": ends.isoformat(),
                "reason": "Checkup",
                "status": "scheduled",
            },
            format="json",
        )
        assert r.status_code == 201
        appt_id = r.data["id"]

        # Receptionist cannot close visit
        close_r = api_client.post(
            f"/api/appointments/{appt_id}/close-visit/", {}, format="json"
        )
        assert close_r.status_code == 403

    def test_receptionist_can_create_invoice_and_record_payment(
        self,
        receptionist,
        client_with_membership,
        patient,
        service,
        api_client,
    ):
        """Behavior: Receptionist can create invoices and record payments."""
        api_client.force_authenticate(user=receptionist)

        r = api_client.post(
            "/api/billing/invoices/",
            {
                "client": client_with_membership.id,
                "patient": patient.id,
                "status": "draft",
                "lines": [
                    {
                        "description": "Consultation",
                        "quantity": 1,
                        "unit_price": "150.00",
                        "service": service.id,
                    },
                ],
            },
            format="json",
        )
        assert r.status_code == 201

        pay_r = api_client.post(
            f"/api/billing/invoices/{r.data['id']}/payments/",
            {"amount": "150.00", "method": "cash", "status": "completed"},
            format="json",
        )
        assert pay_r.status_code == 201

    def test_receptionist_cannot_create_clinical_exam(
        self,
        receptionist,
        appointment,
        api_client,
    ):
        """Behavior: Only doctor (or admin) can create clinical exam."""
        api_client.force_authenticate(user=receptionist)

        r = api_client.post(
            f"/api/appointments/{appointment.id}/exam/",
            {"initial_notes": "Test"},
            format="json",
        )
        assert r.status_code == 403

    def test_doctor_can_perform_exam_and_close_visit(
        self,
        doctor,
        appointment,
        api_client,
    ):
        """Behavior: Doctor can create exam and close visit."""
        api_client.force_authenticate(user=doctor)

        exam_r = api_client.post(
            f"/api/appointments/{appointment.id}/exam/",
            {"initial_notes": "OK"},
            format="json",
        )
        assert exam_r.status_code == 201

        close_r = api_client.post(
            f"/api/appointments/{appointment.id}/close-visit/",
            {},
            format="json",
        )
        assert close_r.status_code in (200, 204)

        appointment.refresh_from_db()
        assert appointment.status == "completed"

    def test_clinic_admin_can_close_visit_like_doctor(
        self,
        clinic_admin,
        appointment,
        api_client,
    ):
        """Behavior: Clinic admin has same clinical powers as doctor."""
        api_client.force_authenticate(user=clinic_admin)
        r = api_client.post(
            f"/api/appointments/{appointment.id}/close-visit/",
            {},
            format="json",
        )
        assert r.status_code in (200, 204)
