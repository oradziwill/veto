"""
EMA Union Product Database (UPD) — read-only API client (skeleton).

Important (verify against current EMA documentation before production use):
- Access may require registration; base URL and auth headers are environment-driven.
- The public read-only API does not include all product documentation (e.g. full SPC /
  package leaflets may only be on the UPD portal). Plan hybrid storage + local notes.
- Rate limits and schema versioning: see EMA technical documentation.

References (as of project planning):
- https://www.ema.europa.eu/ — Union Product Database, veterinary section
- EU newsroom item on read-only API launch (Jan 2025)

This module fetches pages or single resources when `EMA_UPD_BASE_URL` is set.
Implement `parse_*` helpers to map API JSON into `ReferenceProduct` fields when
the exact response shape is confirmed.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class EmaUpdConfigError(RuntimeError):
    """Raised when sync is requested but EMA is not configured."""


def is_configured() -> bool:
    base = getattr(settings, "EMA_UPD_BASE_URL", "") or ""
    return bool(base.strip())


def _client(timeout: float | None = None) -> httpx.Client:
    t = timeout if timeout is not None else float(getattr(settings, "EMA_UPD_TIMEOUT_SEC", 60))
    headers: dict[str, str] = {"Accept": "application/json"}
    token = (getattr(settings, "EMA_UPD_API_TOKEN", "") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(
        base_url=getattr(settings, "EMA_UPD_BASE_URL", "").rstrip("/") + "/",
        headers=headers,
        timeout=t,
    )


def fetch_json(path: str, *, timeout: float | None = None) -> Any:
    """
    GET JSON relative to EMA_UPD_BASE_URL. Used by sync command and tests (mocked).
    """
    if not is_configured():
        raise EmaUpdConfigError("EMA_UPD_BASE_URL is not set")
    rel = path.lstrip("/")
    with _client(timeout=timeout) as client:
        response = client.get(rel)
        response.raise_for_status()
        return response.json()


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:64]


def iter_product_candidates(*, timeout: float | None = None) -> list[dict[str, Any]]:
    """
    Placeholder iterator: when EMA endpoint path is known, replace with real pagination.

    Returns a list of dicts with keys at minimum: external_id, name, common_name, payload.
    Default implementation returns empty list if EMA_UPD_PRODUCTS_PATH is unset.
    """
    path = (getattr(settings, "EMA_UPD_PRODUCTS_PATH", "") or "").strip()
    if not path:
        logger.info("EMA_UPD_PRODUCTS_PATH not set; no remote products fetched.")
        return []
    data = fetch_json(path, timeout=timeout)
    # Accept either {"results": [...]} or a bare list
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
        return [x for x in data["results"] if isinstance(x, dict)]
    logger.warning("Unexpected EMA UPD JSON shape; expected list or dict with results[].")
    return []
