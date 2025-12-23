from __future__ import annotations

from dataclasses import dataclass

from apps.inventory.models import InventoryItem, InventoryMovement
from django.db import transaction
from django.db.models import F


@dataclass(frozen=True)
class MovementResult:
    item: InventoryItem
    movement: InventoryMovement


@transaction.atomic
def apply_movement(
    *,
    clinic_id: int,
    item_id: int,
    kind: str,
    quantity: int,
    created_by,
    note: str = "",
    patient_id: int | None = None,
    appointment_id: int | None = None,
) -> MovementResult:
    """
    Apply a movement and update stock_on_hand atomically.
    Rules:
      - quantity must be > 0 (DB enforces).
      - OUT cannot reduce below 0.
      - ADJUST means: set stock to exact quantity? No.
        For MVP, ADJUST means "delta adjust": positive increases, but we only store positive quantity,
        so ADJUST is treated like IN unless you extend it later.
    """
    item = InventoryItem.objects.select_for_update().get(id=item_id, clinic_id=clinic_id)

    if kind == InventoryMovement.Kind.OUT:
        if item.stock_on_hand - quantity < 0:
            raise ValueError("Insufficient stock for this movement.")

        InventoryItem.objects.filter(id=item.id).update(stock_on_hand=F("stock_on_hand") - quantity)

    elif kind in (InventoryMovement.Kind.IN, InventoryMovement.Kind.ADJUST):
        InventoryItem.objects.filter(id=item.id).update(stock_on_hand=F("stock_on_hand") + quantity)

    else:
        raise ValueError("Invalid movement kind.")

    movement = InventoryMovement.objects.create(
        clinic_id=clinic_id,
        item_id=item.id,
        kind=kind,
        quantity=quantity,
        note=note or "",
        patient_id=patient_id,
        appointment_id=appointment_id,
        created_by=created_by,
    )

    # refresh updated stock value
    item.refresh_from_db(fields=["stock_on_hand", "updated_at"])

    return MovementResult(item=item, movement=movement)
