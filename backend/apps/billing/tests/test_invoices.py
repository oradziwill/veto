from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing.models import Invoice, InvoiceLine
from apps.inventory.models import InventoryItem, InventoryMovement
from apps.scheduling.models import Appointment


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


@pytest.mark.django_db
def test_invoice_line_with_inventory_item_creates_stock_out_movement(
    receptionist,
    doctor,
    client_with_membership,
    patient,
    api_client,
):
    appointment = Appointment.objects.create(
        clinic=receptionist.clinic,
        patient=patient,
        vet=doctor,
        starts_at=timezone.now() + timedelta(hours=1),
        ends_at=timezone.now() + timedelta(hours=2),
        status=Appointment.Status.SCHEDULED,
    )
    item = InventoryItem.objects.create(
        clinic=receptionist.clinic,
        name="Antibiotic X",
        sku="ANTIBIOTIC_X",
        category=InventoryItem.Category.MEDICATION,
        unit="tablet",
        stock_on_hand=20,
        low_stock_threshold=2,
        created_by=doctor,
    )
    api_client.force_authenticate(user=receptionist)
    payload = {
        "client": client_with_membership.id,
        "patient": patient.id,
        "appointment": appointment.id,
        "status": "draft",
        "lines": [
            {
                "description": "Antibiotic dispense",
                "quantity": 3,
                "unit_price": "12.00",
                "inventory_item": item.id,
            }
        ],
    }
    response = api_client.post("/api/billing/invoices/", payload, format="json")
    assert response.status_code == 201
    item.refresh_from_db()
    assert item.stock_on_hand == 17
    movement = InventoryMovement.objects.filter(
        clinic=receptionist.clinic,
        item=item,
        kind=InventoryMovement.Kind.OUT,
        appointment_id=appointment.id,
    ).first()
    assert movement is not None
    assert movement.quantity == 3
    assert "Dispensed in visit" in movement.note


@pytest.mark.django_db
def test_invoice_dispense_rejects_fractional_quantity_for_inventory_item(
    receptionist,
    doctor,
    client_with_membership,
    patient,
    api_client,
):
    item = InventoryItem.objects.create(
        clinic=receptionist.clinic,
        name="Liquid Drug",
        sku="LIQUID_DRUG",
        category=InventoryItem.Category.MEDICATION,
        unit="ml",
        stock_on_hand=50,
        low_stock_threshold=5,
        created_by=doctor,
    )
    api_client.force_authenticate(user=receptionist)
    payload = {
        "client": client_with_membership.id,
        "patient": patient.id,
        "status": "draft",
        "lines": [
            {
                "description": "Liquid dispense",
                "quantity": "1.5",
                "unit_price": "8.00",
                "inventory_item": item.id,
            }
        ],
    }
    response = api_client.post("/api/billing/invoices/", payload, format="json")
    assert response.status_code == 400
    assert "quantity" in str(response.data).lower()
