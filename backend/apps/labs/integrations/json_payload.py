from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils import dateparse

from .dto import IdentifierDraft, ObservationDraft, ParsedIngestPayload


class IngestJsonError(Exception):
    """Invalid inbound JSON for lab ingest."""


def _dec(val: Any) -> Decimal | None:
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def parse_json_payload(raw: bytes | str) -> ParsedIngestPayload:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise IngestJsonError(str(e)) from e

    if not isinstance(data, dict):
        raise IngestJsonError("Payload must be a JSON object")

    idents_raw = data.get("identifiers") or []
    if not isinstance(idents_raw, list):
        raise IngestJsonError("identifiers must be a list")

    identifiers: list[IdentifierDraft] = []
    for i, row in enumerate(idents_raw):
        if not isinstance(row, dict):
            raise IngestJsonError(f"identifiers[{i}] must be an object")
        scheme = row.get("scheme")
        value = row.get("value")
        if not scheme or not value:
            raise IngestJsonError(f"identifiers[{i}] needs scheme and value")
        identifiers.append(IdentifierDraft(scheme=str(scheme), value=str(value)))

    obs_raw = data.get("observations") or data.get("rows") or []
    if not isinstance(obs_raw, list):
        raise IngestJsonError("observations must be a list")

    observations: list[ObservationDraft] = []
    for i, row in enumerate(obs_raw):
        if not isinstance(row, dict):
            raise IngestJsonError(f"observations[{i}] must be an object")
        code = row.get("vendor_code") or row.get("code")
        if not code:
            raise IngestJsonError(f"observations[{i}] needs vendor_code")
        natural_key = str(row.get("natural_key", i))
        obs_at = row.get("observed_at")
        observed_at = None
        if isinstance(obs_at, str):
            observed_at = dateparse.parse_datetime(obs_at)
        elif isinstance(obs_at, datetime):
            observed_at = obs_at
        observations.append(
            ObservationDraft(
                vendor_code=str(code),
                natural_key=natural_key,
                vendor_name=str(row.get("vendor_name") or row.get("name") or ""),
                value_text=str(row.get("value_text") or row.get("value") or ""),
                value_numeric=_dec(row.get("value_numeric")),
                unit=str(row.get("unit") or ""),
                ref_low=str(row.get("ref_low") or ""),
                ref_high=str(row.get("ref_high") or ""),
                abnormal_flag=str(row.get("abnormal_flag") or row.get("flag") or ""),
                result_status=str(row.get("result_status") or ""),
                observed_at=observed_at,
            )
        )

    meta = data.get("metadata")
    metadata: dict[str, Any] = meta if isinstance(meta, dict) else {}

    return ParsedIngestPayload(
        identifiers=identifiers,
        observations=observations,
        metadata=metadata,
    )
