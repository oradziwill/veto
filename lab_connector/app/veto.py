from __future__ import annotations

import httpx

from app.config import Settings


def deliver_ingest(settings: Settings, body: bytes, *, timeout_sec: float = 60.0) -> tuple[bool, str]:
    """
    POST JSON to Veto lab ingest. Returns (success, message).
    2xx = success (including 200 duplicate idempotency).
    """
    url = settings.ingest_url()
    headers = {
        "X-Lab-Ingest-Token": settings.veto_ingest_token,
        "Content-Type": "application/json; charset=utf-8",
    }
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            r = client.post(url, content=body, headers=headers)
    except httpx.RequestError as e:
        return False, f"network:{e}"

    if 200 <= r.status_code < 300:
        return True, f"http_{r.status_code}"
    if 400 <= r.status_code < 500:
        return False, f"client_{r.status_code}:{r.text[:500]}"
    return False, f"server_{r.status_code}:{r.text[:500]}"
