import pytest

from apps.billing.models import Invoice, InvoiceLine


@pytest.mark.django_db
def test_create_invoice_with_lines(
    receptionist,
    client_with_membership,
    patient,
    service,
    api_client,
):
    """Receptionist can create invoice with service line items."""
    api_client.force_authenticate(user=receptionist)

    payload = {
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
    }
    r = api_client.post("/api/billing/invoices/", payload, format="json")
    assert r.status_code == 201
    assert r.data["status"] == "draft"
    assert len(r.data["lines"]) == 1
    assert r.data["lines"][0]["line_total"] == "150.00"
    assert r.data["total"] == "150.00"


@pytest.mark.django_db
def test_record_payment(
    receptionist,
    client_with_membership,
    patient,
    api_client,
):
    """Recording full payment marks invoice as paid."""
    invoice = Invoice.objects.create(
        clinic=receptionist.clinic,
        client=client_with_membership,
        patient=patient,
        status="draft",
    )
    InvoiceLine.objects.create(
        invoice=invoice,
        description="Consultation",
        quantity=1,
        unit_price=150,
    )

    api_client.force_authenticate(user=receptionist)
    r = api_client.post(
        f"/api/billing/invoices/{invoice.id}/payments/",
        {"amount": "150.00", "method": "cash", "status": "completed"},
        format="json",
    )
    assert r.status_code == 201
    invoice.refresh_from_db()
    assert invoice.status == "paid"
