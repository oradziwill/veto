"""
Upsert helpers for ReferenceProduct rows from EMA (or test) payloads.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.drug_catalog.models import ReferenceProduct
from apps.drug_catalog.services import ema_upd


def normalize_remote_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    """
    Map a generic API dict to fields. Extend when EMA response shape is fixed.
    """
    ext_id = (
        raw.get("external_id") or raw.get("id") or raw.get("productId") or raw.get("product_id")
    )
    if ext_id is None or str(ext_id).strip() == "":
        return None
    ext_id = str(ext_id).strip()
    name = (raw.get("name") or raw.get("productName") or raw.get("trade_name") or "").strip()
    if not name:
        name = ext_id
    common_name = (raw.get("common_name") or raw.get("international_name") or "").strip()
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        payload = {
            k: v for k, v in raw.items() if k not in ("external_id", "id", "name", "common_name")
        }
    return {
        "external_id": ext_id,
        "name": name,
        "common_name": common_name,
        "payload": payload,
    }


def upsert_ema_product_row(raw: dict[str, Any]) -> ReferenceProduct:
    normalized = normalize_remote_row(raw)
    if not normalized:
        raise ValueError("Cannot normalize row (missing id)")
    payload = normalized["payload"]
    source_hash = ema_upd.stable_hash(payload)
    obj, _ = ReferenceProduct.objects.update_or_create(
        external_source=ReferenceProduct.ExternalSource.EMA_UPD,
        external_id=normalized["external_id"],
        defaults={
            "name": normalized["name"],
            "common_name": normalized["common_name"],
            "payload": payload,
            "last_synced_at": timezone.now(),
            "source_hash": source_hash,
        },
    )
    return obj


def run_ema_sync(*, incremental: bool = False) -> tuple[int, dict[str, Any]]:
    """
    Fetch candidates and upsert. Returns (count, detail dict).
    """
    rows = ema_upd.iter_product_candidates()
    detail: dict[str, Any] = {"incremental": incremental, "remote_rows": len(rows)}
    n = 0
    errors: list[str] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        try:
            upsert_ema_product_row(raw)
            n += 1
        except (ValueError, TypeError) as exc:
            errors.append(str(exc))
    detail["errors"] = errors[:50]
    return n, detail
