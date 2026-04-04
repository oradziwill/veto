import pytest
from apps.accounts.models import User
from apps.inventory.models import InventoryItem
from apps.tenancy.models import Clinic
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_create_item_with_barcode_and_resolve():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username="u1", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user=user)

    ean = "5901234123457"
    payload = {
        "name": "Wholesale Drug",
        "sku": "internal_sku_1",
        "barcode": "590 1234 1234 57",  # spaces stripped → digits
        "category": "medication",
        "unit": "pcs",
        "stock_on_hand": 0,
        "low_stock_threshold": 0,
    }
    r = client.post("/api/inventory/items/", payload, format="json")
    assert r.status_code == 201
    assert r.data["barcode"] == ean

    r2 = client.get("/api/inventory/items/resolve_barcode/", {"code": ean})
    assert r2.status_code == 200
    assert r2.data["id"] == r.data["id"]
    assert r2.data["barcode"] == ean


@pytest.mark.django_db
def test_duplicate_barcode_same_clinic_rejected():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username="u1", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user=user)

    ean = "5901234123457"
    base = {
        "name": "A",
        "sku": "SKU_A",
        "barcode": ean,
        "category": "medication",
        "unit": "u",
        "stock_on_hand": 0,
        "low_stock_threshold": 0,
    }
    assert client.post("/api/inventory/items/", base, format="json").status_code == 201
    r2 = client.post(
        "/api/inventory/items/",
        {**base, "name": "B", "sku": "SKU_B"},
        format="json",
    )
    assert r2.status_code == 400
    assert "barcode" in r2.data


@pytest.mark.django_db
def test_resolve_barcode_404_when_unknown():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username="u1", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user=user)

    r = client.get("/api/inventory/items/resolve_barcode/", {"code": "5901234123457"})
    assert r.status_code == 404


@pytest.mark.django_db
def test_list_filter_barcode_exact_query_param():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username="u1", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )
    InventoryItem.objects.create(
        clinic=clinic,
        name="X",
        sku="S1",
        barcode="5901234123457",
        category=InventoryItem.Category.MEDICATION,
        unit="u",
        stock_on_hand=1,
        low_stock_threshold=0,
        created_by=user,
    )
    InventoryItem.objects.create(
        clinic=clinic,
        name="Y",
        sku="S2",
        barcode="5909999999999",
        category=InventoryItem.Category.MEDICATION,
        unit="u",
        stock_on_hand=1,
        low_stock_threshold=0,
        created_by=user,
    )
    client = APIClient()
    client.force_authenticate(user=user)

    r = client.get("/api/inventory/items/", {"barcode": "5901234123457"})
    assert r.status_code == 200
    assert len(r.data) == 1
    assert r.data[0]["sku"] == "S1"


@pytest.mark.django_db
def test_q_search_includes_barcode_substring():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username="u1", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )
    InventoryItem.objects.create(
        clinic=clinic,
        name="Hidden",
        sku="ZZZ",
        barcode="5901234123457",
        category=InventoryItem.Category.MEDICATION,
        unit="u",
        stock_on_hand=1,
        low_stock_threshold=0,
        created_by=user,
    )
    client = APIClient()
    client.force_authenticate(user=user)

    r = client.get("/api/inventory/items/", {"q": "5901234"})
    assert r.status_code == 200
    assert len(r.data) >= 1
    assert any(row.get("barcode") == "5901234123457" for row in r.data)


@pytest.mark.django_db
def test_resolve_barcode_requires_code():
    clinic = Clinic.objects.create(name="C1", address="a", phone="p", email="e@e.com")
    user = User.objects.create_user(
        username="u1", password="pass", clinic=clinic, is_vet=True, is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user=user)

    r = client.get("/api/inventory/items/resolve_barcode/")
    assert r.status_code == 400
