from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.billing.models import Invoice, InvoiceLine
from apps.clients.models import Client, ClientClinic
from apps.inventory.models import InventoryItem
from apps.patients.models import Patient
from apps.tenancy.models import Clinic
from django.utils import timezone


@pytest.mark.django_db
def test_recent_supply_lines_empty(api_client, receptionist, patient):
    api_client.force_authenticate(user=receptionist)
    r = api_client.get(f"/api/patients/{patient.id}/recent-supply-lines/")
    assert r.status_code == 200
    assert r.data == []


@pytest.mark.django_db
def test_recent_supply_lines_dedupes_by_inventory_newest_first(api_client, receptionist, doctor):
    clinic = receptionist.clinic
    owner = Client.objects.create(first_name="A", last_name="B")
    ClientClinic.objects.create(client=owner, clinic=clinic)
    patient = Patient.objects.create(clinic=clinic, owner=owner, name="Pet", species="dog")

    item_a = InventoryItem.objects.create(
        clinic=clinic,
        name="Gel",
        sku="GEL-1",
        unit="but",
        stock_on_hand=10,
        created_by=doctor,
    )
    item_b = InventoryItem.objects.create(
        clinic=clinic,
        name="Wipe",
        sku="WIP-1",
        unit="szt",
        stock_on_hand=5,
        created_by=doctor,
    )

    inv_old = Invoice.objects.create(
        clinic=clinic,
        client=owner,
        patient=patient,
        status=Invoice.Status.DRAFT,
    )
    InvoiceLine.objects.create(
        invoice=inv_old,
        description=item_a.name,
        quantity=Decimal("2"),
        unit_price=Decimal("10"),
        inventory_item=item_a,
        unit="but",
    )
    InvoiceLine.objects.create(
        invoice=inv_old,
        description=item_b.name,
        quantity=Decimal("1"),
        unit_price=Decimal("5"),
        inventory_item=item_b,
        unit="szt",
    )

    inv_new = Invoice.objects.create(
        clinic=clinic,
        client=owner,
        patient=patient,
        status=Invoice.Status.DRAFT,
    )
    InvoiceLine.objects.create(
        invoice=inv_new,
        description=item_a.name,
        quantity=Decimal("3"),
        unit_price=Decimal("10"),
        inventory_item=item_a,
        unit="but",
    )

    api_client.force_authenticate(user=receptionist)
    r = api_client.get(f"/api/patients/{patient.id}/recent-supply-lines/")
    assert r.status_code == 200
    assert len(r.data) == 2
    # New invoice first for item A → quantity 3, then item B from older invoice
    assert r.data[0]["inventory_item_id"] == item_a.id
    assert r.data[0]["last_quantity"] in ("3", "3.000")
    assert r.data[0]["invoice_id"] == inv_new.id
    assert r.data[1]["inventory_item_id"] == item_b.id
    assert r.data[1]["last_quantity"] in ("1", "1.000")
    assert r.data[1]["invoice_id"] == inv_old.id


@pytest.mark.django_db
def test_recent_supply_lines_respects_limit_param(
    api_client, receptionist, doctor, patient, client_with_membership
):
    clinic = receptionist.clinic
    for i in range(3):
        item = InventoryItem.objects.create(
            clinic=clinic,
            name=f"Item{i}",
            sku=f"SKU-{i}",
            unit="szt",
            stock_on_hand=10,
            created_by=doctor,
        )
        inv = Invoice.objects.create(
            clinic=clinic,
            client=client_with_membership,
            patient=patient,
            status=Invoice.Status.DRAFT,
            created_at=timezone.now() - timedelta(seconds=10 - i),
        )
        InvoiceLine.objects.create(
            invoice=inv,
            description=item.name,
            quantity=1,
            unit_price=Decimal("1"),
            inventory_item=item,
            unit="szt",
        )

    api_client.force_authenticate(user=receptionist)
    r = api_client.get(f"/api/patients/{patient.id}/recent-supply-lines/?limit=2")
    assert r.status_code == 200
    assert len(r.data) == 2


@pytest.mark.django_db
def test_recent_supply_lines_other_clinic_patient_404(api_client, receptionist):
    other = Clinic.objects.create(name="O", address="a", phone="p", email="e@e.com")
    owner = Client.objects.create(first_name="X", last_name="Y")
    ClientClinic.objects.create(client=owner, clinic=other)
    foreign_patient = Patient.objects.create(clinic=other, owner=owner, name="F", species="cat")

    api_client.force_authenticate(user=receptionist)
    r = api_client.get(f"/api/patients/{foreign_patient.id}/recent-supply-lines/")
    assert r.status_code == 404
