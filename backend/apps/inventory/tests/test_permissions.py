import pytest
from apps.accounts.models import User
from apps.inventory.models import InventoryItem
from apps.tenancy.models import Clinic
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_inventory_movement_cannot_use_item_from_other_clinic():
    c1 = Clinic.objects.create(name="C1", address="a", phone="p", email="e1@test.com")
    c2 = Clinic.objects.create(name="C2", address="a", phone="p", email="e2@test.com")

    u1 = User.objects.create_user(username="u1", password="pass", clinic=c1, is_staff=True)
    item_c2 = InventoryItem.objects.create(
        clinic=c2,
        name="Other Clinic Item",
        sku="OTHER_1",
        category="other",
        unit="pcs",
        stock_on_hand=10,
        low_stock_threshold=0,
        created_by=u1,  # created_by doesn't matter for this test
    )

    client = APIClient()
    client.force_authenticate(user=u1)

    resp = client.post(
        "/api/inventory/movements/",
        {"item": item_c2.id, "kind": "out", "quantity": 1, "note": "x"},
        format="json",
    )
    assert resp.status_code == 400
    assert "item" in resp.data
