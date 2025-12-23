import pytest
from apps.accounts.models import User
from apps.inventory.models import InventoryItem, InventoryMovement
from apps.inventory.services.stock import StockError, apply_inventory_movement
from apps.tenancy.models import Clinic


@pytest.mark.django_db
def test_out_movement_rejects_insufficient_stock():
    clinic = Clinic.objects.create(name="C1", address="x", phone="x", email="x@x.com")
    user = User.objects.create(username="u1", clinic=clinic, is_vet=True)

    item = InventoryItem.objects.create(
        clinic=clinic,
        name="Item",
        sku="ITEM",
        category=InventoryItem.Category.OTHER,
        unit="pcs",
        stock_on_hand=3,
        low_stock_threshold=0,
        created_by=user,
    )

    with pytest.raises(StockError):
        apply_inventory_movement(
            clinic_id=clinic.id,
            item_id=item.id,
            kind=InventoryMovement.Kind.OUT,
            quantity=5,
        )


@pytest.mark.django_db
def test_in_and_out_apply_correctly():
    clinic = Clinic.objects.create(name="C1", address="x", phone="x", email="x@x.com")
    user = User.objects.create(username="u1", clinic=clinic, is_vet=True)

    item = InventoryItem.objects.create(
        clinic=clinic,
        name="Item",
        sku="ITEM",
        category=InventoryItem.Category.OTHER,
        unit="pcs",
        stock_on_hand=10,
        low_stock_threshold=0,
        created_by=user,
    )

    apply_inventory_movement(
        clinic_id=clinic.id,
        item_id=item.id,
        kind=InventoryMovement.Kind.IN,
        quantity=7,
    )
    item.refresh_from_db()
    assert item.stock_on_hand == 17

    apply_inventory_movement(
        clinic_id=clinic.id,
        item_id=item.id,
        kind=InventoryMovement.Kind.OUT,
        quantity=5,
    )
    item.refresh_from_db()
    assert item.stock_on_hand == 12


@pytest.mark.django_db
def test_adjust_sets_absolute_value():
    clinic = Clinic.objects.create(name="C1", address="x", phone="x", email="x@x.com")
    user = User.objects.create(username="u1", clinic=clinic, is_vet=True)

    item = InventoryItem.objects.create(
        clinic=clinic,
        name="Item",
        sku="ITEM",
        category=InventoryItem.Category.OTHER,
        unit="pcs",
        stock_on_hand=10,
        low_stock_threshold=0,
        created_by=user,
    )

    apply_inventory_movement(
        clinic_id=clinic.id,
        item_id=item.id,
        kind=InventoryMovement.Kind.ADJUST,
        quantity=100,
    )
    item.refresh_from_db()
    assert item.stock_on_hand == 100
