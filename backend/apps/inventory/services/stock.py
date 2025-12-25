from __future__ import annotations

from dataclasses import dataclass

from apps.inventory.models import InventoryItem, InventoryMovement
from django.db import transaction
from django.db.models import F


@dataclass(frozen=True)
class StockResult:
    item_id: int
    previous_stock: int
    new_stock: int
    movement_id: int


@transaction.atomic
def apply_stock_movement(
    *,
    clinic_id: int,
    item_id: int,
    kind: str,
    quantity: int,
    created_by_id: int,
    note: str = "",
    patient_id: int | None = None,
    appointment_id: int | None = None,
) -> StockResult:
    """
    Applies a stock movement and updates InventoryItem.stock_on_hand.

    Rules:
    - IN:      +quantity
    - OUT:     -quantity
    - ADJUST:  set stock_on_hand = quantity  (absolute stocktake)
    """
    item = InventoryItem.objects.select_for_update().get(pk=item_id, clinic_id=clinic_id)
    previous = int(item.stock_on_hand)

    if kind == InventoryMovement.Kind.IN:
        InventoryItem.objects.filter(pk=item.pk).update(stock_on_hand=F("stock_on_hand") + quantity)
    elif kind == InventoryMovement.Kind.OUT:
        InventoryItem.objects.filter(pk=item.pk).update(stock_on_hand=F("stock_on_hand") - quantity)
    elif kind == InventoryMovement.Kind.ADJUST:
        InventoryItem.objects.filter(pk=item.pk).update(stock_on_hand=quantity)
    else:
        raise ValueError(f"Unknown movement kind: {kind}")

    movement = InventoryMovement.objects.create(
        clinic_id=clinic_id,
        item_id=item.pk,
        kind=kind,
        quantity=quantity,
        note=note or "",
        patient_id=patient_id,
        appointment_id=appointment_id,
        created_by_id=created_by_id,
    )

    item.refresh_from_db(fields=["stock_on_hand"])
    new = int(item.stock_on_hand)

    return StockResult(
        item_id=item.pk, previous_stock=previous, new_stock=new, movement_id=movement.pk
    )
