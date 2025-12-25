from __future__ import annotations

from dataclasses import dataclass

from apps.inventory.models import InventoryItem, InventoryMovement
from django.db import transaction


@dataclass(frozen=True)
class StockChange:
    new_stock_on_hand: int


def apply_movement(movement: InventoryMovement) -> StockChange:
    """
    Apply a single InventoryMovement to its InventoryItem.stock_on_hand.

    Rules:
      - kind="in":     stock += quantity
      - kind="out":    stock -= quantity (cannot go below 0)
      - kind="adjust": stock = quantity (absolute set)
    """
    if movement.quantity is None or movement.quantity <= 0:
        raise ValueError("quantity must be > 0")

    # Ensure we apply under transaction and lock the row to avoid race conditions.
    with transaction.atomic():
        item = InventoryItem.objects.select_for_update().get(pk=movement.item_id)

        kind = movement.kind
        qty = int(movement.quantity)

        if kind == InventoryMovement.Kind.IN:
            new_val = item.stock_on_hand + qty
        elif kind == InventoryMovement.Kind.OUT:
            new_val = item.stock_on_hand - qty
            if new_val < 0:
                raise ValueError("Insufficient stock on hand.")
        elif kind == InventoryMovement.Kind.ADJUST:
            new_val = qty
        else:
            raise ValueError("Invalid movement kind.")

        item.stock_on_hand = new_val
        item.save(update_fields=["stock_on_hand", "updated_at"])

    return StockChange(new_stock_on_hand=new_val)
