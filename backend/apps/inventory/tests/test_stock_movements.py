import pytest
from apps.accounts.models import User
from apps.inventory.models import InventoryItem
from apps.tenancy.models import Clinic
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_create_inventory_item_and_unique_sku_per_clinic():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username="u1", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )

    client = APIClient()
    client.force_authenticate(user=user)

    payload = {
        "name": "Bandage Roll",
        "sku": "bandage roll",  # should normalize to BANDAGE_ROLL
        "category": "supply",
        "unit": "rolls",
        "stock_on_hand": 20,
        "low_stock_threshold": 10,
    }

    r1 = client.post("/api/inventory/items/", payload, format="json")
    assert r1.status_code == 201
    assert r1.data["sku"] == "BANDAGE_ROLL"

    r2 = client.post("/api/inventory/items/", payload, format="json")
    assert r2.status_code == 400
    assert "sku" in r2.data


@pytest.mark.django_db
def test_stock_out_decrements_stock_on_hand():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username="u1", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )

    item = InventoryItem.objects.create(
        clinic=clinic,
        name="Antibiotic A",
        sku="ANTIBIOTIC_A",
        category=InventoryItem.Category.MEDICATION,
        unit="vials",
        stock_on_hand=50,
        low_stock_threshold=10,
        created_by=user,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    r = client.post(
        "/api/inventory/movements/",
        {"item": item.id, "kind": "out", "quantity": 5, "note": "dispensed"},
        format="json",
    )
    assert r.status_code == 201

    item.refresh_from_db()
    assert item.stock_on_hand == 45


@pytest.mark.django_db
def test_adjust_sets_absolute_stock_on_hand():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username="u1", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )

    item = InventoryItem.objects.create(
        clinic=clinic,
        name="Gloves",
        sku="GLOVES",
        category=InventoryItem.Category.SUPPLY,
        unit="boxes",
        stock_on_hand=25,
        low_stock_threshold=30,
        created_by=user,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    r = client.post(
        "/api/inventory/movements/",
        {"item": item.id, "kind": "adjust", "quantity": 100, "note": "stocktake"},
        format="json",
    )
    assert r.status_code == 201

    item.refresh_from_db()
    assert item.stock_on_hand == 100


@pytest.mark.django_db
def test_low_stock_filter_and_is_low_stock_field():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username="u1", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )

    InventoryItem.objects.create(
        clinic=clinic,
        name="Low",
        sku="LOW",
        category=InventoryItem.Category.SUPPLY,
        unit="x",
        stock_on_hand=5,
        low_stock_threshold=10,
        created_by=user,
    )
    InventoryItem.objects.create(
        clinic=clinic,
        name="Ok",
        sku="OK",
        category=InventoryItem.Category.SUPPLY,
        unit="x",
        stock_on_hand=50,
        low_stock_threshold=10,
        created_by=user,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    r = client.get("/api/inventory/items/?low_stock=true")
    assert r.status_code == 200
    assert len(r.data) == 1
    assert r.data[0]["sku"] == "LOW"
    assert r.data[0]["is_low_stock"] is True
