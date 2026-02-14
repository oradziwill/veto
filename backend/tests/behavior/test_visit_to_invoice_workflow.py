"""
Behavior: Full visit-to-invoice workflow.

As a receptionist and doctor, I can:
1. Book an appointment for a client's pet
2. Doctor performs clinical exam during the visit
3. Doctor closes the visit
4. Receptionist creates an invoice for the visit
5. Receptionist records payment and invoice becomes paid
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.billing.models import Invoice
from apps.scheduling.models import Appointment


@pytest.mark.django_db
class TestVisitToInvoiceWorkflow:
    """End-to-end: schedule visit → exam → close → invoice → pay."""

    def test_full_workflow_receptionist_books_doctor_examines_receptionist_bills(
        self,
        clinic,
        doctor,
        receptionist,
        client_with_membership,
        patient,
        service,
        api_client,
    ):
        """
        Behavior: Receptionist books appointment, doctor performs exam and closes visit,
        receptionist creates invoice and records full payment.
        """
        # 1. Receptionist books appointment
        api_client.force_authenticate(user=receptionist)
        today = timezone.now()
        starts = today.replace(hour=14, minute=0, second=0, microsecond=0)
        ends = today.replace(hour=14, minute=30, second=0, microsecond=0)

        book_resp = api_client.post(
            "/api/appointments/",
            {
                "patient": patient.id,
                "vet": doctor.id,
                "starts_at": starts.isoformat(),
                "ends_at": ends.isoformat(),
                "reason": "Vaccination",
                "status": "scheduled",
            },
            format="json",
        )
        assert book_resp.status_code == 201
        appt_id = book_resp.data["id"]

        # 2. Doctor performs clinical exam
        api_client.force_authenticate(user=doctor)
        exam_resp = api_client.post(
            f"/api/appointments/{appt_id}/exam/",
            {
                "initial_notes": "Pet in good condition",
                "temperature_c": "38.5",
                "initial_diagnosis": "Healthy",
            },
            format="json",
        )
        assert exam_resp.status_code == 201

        # 3. Doctor closes the visit
        close_resp = api_client.post(
            f"/api/appointments/{appt_id}/close-visit/",
            {},
            format="json",
        )
        assert close_resp.status_code in (200, 204)

        appt = Appointment.objects.get(pk=appt_id)
        assert appt.status == "completed"

        # 4. Receptionist creates invoice for the visit
        api_client.force_authenticate(user=receptionist)
        invoice_resp = api_client.post(
            "/api/billing/invoices/",
            {
                "client": client_with_membership.id,
                "patient": patient.id,
                "appointment": appt_id,
                "status": "draft",
                "lines": [
                    {
                        "description": "Consultation",
                        "quantity": 1,
                        "unit_price": str(service.price),
                        "service": service.id,
                    },
                ],
            },
            format="json",
        )
        assert invoice_resp.status_code == 201
        assert invoice_resp.data["status"] == "draft"
        invoice_id = invoice_resp.data["id"]
        total = float(invoice_resp.data["total"])

        # 5. Receptionist records full payment
        pay_resp = api_client.post(
            f"/api/billing/invoices/{invoice_id}/payments/",
            {
                "amount": str(total),
                "method": "card",
                "status": "completed",
            },
            format="json",
        )
        assert pay_resp.status_code == 201

        inv = Invoice.objects.get(pk=invoice_id)
        assert inv.status == "paid"

    def test_partial_payment_keeps_invoice_sent_until_fully_paid(
        self,
        receptionist,
        client_with_membership,
        patient,
        service,
        api_client,
    ):
        """Behavior: Multiple partial payments; invoice becomes paid only when fully covered."""
        api_client.force_authenticate(user=receptionist)

        inv_resp = api_client.post(
            "/api/billing/invoices/",
            {
                "client": client_with_membership.id,
                "patient": patient.id,
                "status": "draft",
                "lines": [
                    {"description": "Consultation", "quantity": 1, "unit_price": "200.00"},
                ],
            },
            format="json",
        )
        assert inv_resp.status_code == 201
        invoice_id = inv_resp.data["id"]

        # First partial payment
        api_client.post(
            f"/api/billing/invoices/{invoice_id}/payments/",
            {"amount": "100.00", "method": "cash", "status": "completed"},
            format="json",
        )
        inv = Invoice.objects.get(pk=invoice_id)
        assert inv.status != "paid"  # not fully paid yet

        # Second payment completes it
        api_client.post(
            f"/api/billing/invoices/{invoice_id}/payments/",
            {"amount": "100.00", "method": "cash", "status": "completed"},
            format="json",
        )
        inv.refresh_from_db()
        assert inv.status == "paid"
