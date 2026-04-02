from __future__ import annotations

from apps.billing.models import Invoice, InvoiceLine


def recent_supply_line_suggestions(*, clinic_id: int, patient_id: int, limit: int) -> list[dict]:
    """
    One row per distinct inventory item, newest invoice first (read-only suggestions).
    Draft and cancelled invoices are ignored (only finalized-like billing counts).
    """
    lines = (
        InvoiceLine.objects.filter(
            invoice__clinic_id=clinic_id,
            invoice__patient_id=patient_id,
            inventory_item_id__isnull=False,
        )
        .exclude(
            invoice__status__in=(Invoice.Status.CANCELLED, Invoice.Status.DRAFT),
        )
        .select_related("invoice", "inventory_item")
        .order_by("-invoice__created_at", "-invoice__id", "-id")
    )

    seen: set[int] = set()
    out: list[dict] = []
    for line in lines:
        iid = line.inventory_item_id
        if iid in seen:
            continue
        seen.add(iid)
        item = line.inventory_item
        q = line.quantity
        out.append(
            {
                "inventory_item_id": iid,
                "name": item.name,
                "sku": item.sku,
                "unit": line.unit,
                "last_quantity": str(q),
                "last_used_at": line.invoice.created_at.isoformat(),
                "invoice_id": line.invoice.id,
            }
        )
        if len(out) >= limit:
            break
    return out
