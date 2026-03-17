from __future__ import annotations

from datetime import timedelta

import pytest
from apps.accounts.models import User
from apps.billing.models import Invoice, InvoiceLine
from apps.clients.models import Client, ClientClinic
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.tenancy.models import Clinic
from django.utils import timezone


@pytest.mark.django_db
def test_patient_history_create_accepts_invoice_and_appointment_and_exposes_services(
    api_client, doctor, clinic, patient, client_with_membership
):
    appointment = Appointment.objects.create(
        clinic=clinic,
        patient=patient,
        vet=doctor,
        starts_at=timezone.now() + timedelta(hours=1),
        ends_at=timezone.now() + timedelta(hours=2),
        status=Appointment.Status.SCHEDULED,
    )
    invoice = Invoice.objects.create(
        clinic=clinic,
        client=client_with_membership,
        patient=patient,
        appointment=appointment,
        status=Invoice.Status.DRAFT,
    )
    InvoiceLine.objects.create(
        invoice=invoice,
        description="Consultation",
        quantity=1,
        unit_price="150.00",
    )
    InvoiceLine.objects.create(
        invoice=invoice,
        description="Bandage",
        quantity=2,
        unit_price="12.00",
    )

    api_client.force_authenticate(user=doctor)
    create = api_client.post(
        f"/api/patients/{patient.id}/history/",
        {
            "note": "Patient stable after visit.",
            "appointment": appointment.id,
            "invoice": invoice.id,
        },
        format="json",
    )
    assert create.status_code == 201
    assert create.data["invoice"] == invoice.id
    assert create.data["appointment"]["id"] == appointment.id
    assert len(create.data["services_performed"]) == 2
    assert create.data["services_performed"][0]["description"] == "Consultation"
    assert create.data["services_performed"][0]["quantity"] == "1.000"

    listing = api_client.get(f"/api/patients/{patient.id}/history/")
    assert listing.status_code == 200
    assert len(listing.data) == 1
    assert listing.data[0]["invoice"] == invoice.id
    assert listing.data[0]["services_performed"][1]["description"] == "Bandage"


@pytest.mark.django_db
def test_patient_history_create_rejects_foreign_clinic_invoice(
    api_client, doctor, clinic, patient, client_with_membership
):
    other_clinic = Clinic.objects.create(
        name="Clinic B",
        address="Street 2",
        phone="+48222222222",
        email="b@example.com",
    )
    other_owner = Client.objects.create(
        first_name="Other",
        last_name="Owner",
        email="other.owner@example.com",
    )
    ClientClinic.objects.create(client=other_owner, clinic=other_clinic, is_active=True)
    other_doctor = User.objects.create_user(
        username="doctor_history_other",
        password="pass",
        clinic=other_clinic,
        role=User.Role.DOCTOR,
        is_vet=True,
    )
    other_patient = Patient.objects.create(
        clinic=other_clinic,
        owner=other_owner,
        name="OtherPet",
        species="Dog",
        primary_vet=other_doctor,
    )
    foreign_invoice = Invoice.objects.create(
        clinic=other_clinic,
        client=other_owner,
        patient=other_patient,
        status=Invoice.Status.DRAFT,
    )

    api_client.force_authenticate(user=doctor)
    create = api_client.post(
        f"/api/patients/{patient.id}/history/",
        {"note": "Attempt bad invoice link", "invoice": foreign_invoice.id},
        format="json",
    )
    assert create.status_code == 400
    assert "invoice" in create.data
