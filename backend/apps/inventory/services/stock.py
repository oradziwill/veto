from __future__ import annotations

from dataclasses import dataclass

from apps.inventory.models import InventoryItem, InventoryMovement
from django.db import transaction
from django.db.models import F


class StockError(Exception):
    """Domain-level stock error (converted to DRF validation error in the API layer)."""


@dataclass(frozen=True)
class StockResult:
    item_id: int
    previous_stock: int
    new_stock: int


@transaction.atomic
def apply_inventory_movement(
    *,
    clinic_id: int,
    item_id: int,
    kind: str,
    quantity: int,
) -> StockResult:
    """
    Apply a movement to an inventory item atomically.

    Rules:
    - IN: stock_on_hand += quantity
    - OUT: stock_on_hand -= quantity (must not go below 0)
    - ADJUST: stock_on_hand = quantity (absolute)

    Concurrency:
    - Uses select_for_update() to prevent race conditions.
    """
    if quantity is None or quantity <= 0:
        raise StockError("quantity must be > 0")

    # Lock the row for update within this transaction
    item = (
        InventoryItem.objects.select_for_update()
        .only("id", "clinic_id", "stock_on_hand")
        .get(id=item_id, clinic_id=clinic_id)
    )

    previous = int(item.stock_on_hand)

    if kind == InventoryMovement.Kind.IN:
        InventoryItem.objects.filter(id=item.id).update(stock_on_hand=F("stock_on_hand") + quantity)
        new_stock = previous + quantity

    elif kind == InventoryMovement.Kind.OUT:
        if previous - quantity < 0:
            raise StockError("Insufficient stock for this OUT movement.")
        InventoryItem.objects.filter(id=item.id).update(stock_on_hand=F("stock_on_hand") - quantity)
        new_stock = previous - quantity

    elif kind == InventoryMovement.Kind.ADJUST:
        if quantity < 0:
            raise StockError("adjust quantity must be >= 0")
        InventoryItem.objects.filter(id=item.id).update(stock_on_hand=quantity)
        new_stock = quantity

    else:
        raise StockError("Invalid movement kind.")

    return StockResult(item_id=item.id, previous_stock=previous, new_stock=new_stock)
