"""Portal Idempotency-Key handling (Stripe-style replay for safe retries)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import IntegrityError, transaction
from rest_framework.response import Response

from apps.portal.models import PortalIdempotencyRecord

_IDEMPOTENCY_MAX_LEN = 128


def parse_portal_idempotency_key(request) -> str | None | bool:
    """
    Returns:
        None — header absent; idempotency disabled.
        False — header present but invalid (empty or too long).
        str — usable key.
    """
    if "HTTP_IDEMPOTENCY_KEY" not in request.META:
        return None
    raw = (request.META.get("HTTP_IDEMPOTENCY_KEY") or "").strip()
    if not raw or len(raw) > _IDEMPOTENCY_MAX_LEN:
        return False
    return raw


def idempotency_key_invalid_response() -> Response:
    return Response(
        {
            "detail": (
                f"Idempotency-Key must be non-empty and at most {_IDEMPOTENCY_MAX_LEN} characters."
            )
        },
        status=400,
    )


def hash_portal_request_payload(data: dict[str, Any]) -> str:
    normalized = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def replay_or_begin_idempotent_request(
    *,
    client_id: int,
    clinic_id: int,
    operation: str,
    idempotency_key: str,
    body_hash: str,
) -> tuple[PortalIdempotencyRecord | None, Response | None]:
    """
    Within an open atomic block, acquire or create the idempotency row (locked).

    Returns:
        (None, Response) — caller must return the Response (replay or 409).
        (record, None) — caller should run the operation and call
            :func:`complete_idempotent_request` on the same ``record``.
    """
    try:
        with transaction.atomic():
            record = PortalIdempotencyRecord.objects.create(
                client_id=client_id,
                clinic_id=clinic_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_hash=body_hash,
                response_status=None,
                response_body=None,
            )
    except IntegrityError:
        record = None
    else:
        return record, None

    record = PortalIdempotencyRecord.objects.select_for_update().get(
        client_id=client_id,
        clinic_id=clinic_id,
        operation=operation,
        idempotency_key=idempotency_key,
    )
    if record.request_hash != body_hash:
        return None, Response(
            {"detail": "Idempotency-Key was used with a different request body."},
            status=409,
        )
    if record.response_status is not None:
        body = record.response_body if isinstance(record.response_body, dict) else {}
        return None, Response(body, status=record.response_status)
    return record, None


def complete_idempotent_request(record: PortalIdempotencyRecord, response: Response) -> Response:
    record.response_status = response.status_code
    try:
        data = response.data  # type: ignore[attr-defined]
        record.response_body = dict(data) if hasattr(data, "keys") else {}
    except Exception:
        record.response_body = {}
    record.save(update_fields=["response_status", "response_body"])
    return response


def run_idempotent_portal_post(
    *,
    request,
    client_id: int,
    clinic_id: int,
    operation: str,
    payload_for_hash: dict[str, Any],
    handler,
) -> Response:
    """
    If ``Idempotency-Key`` is absent, runs ``handler()`` and returns its Response.

    If present, stores/replays the response keyed by (client, clinic, operation, key).
    ``handler`` is called with no arguments inside ``transaction.atomic()`` and must
    return a :class:`rest_framework.response.Response`.
    """
    key = parse_portal_idempotency_key(request)
    if key is False:
        return idempotency_key_invalid_response()
    if key is None:
        return handler()

    assert isinstance(key, str)
    body_hash = hash_portal_request_payload(payload_for_hash)

    with transaction.atomic():
        record, early = replay_or_begin_idempotent_request(
            client_id=client_id,
            clinic_id=clinic_id,
            operation=operation,
            idempotency_key=key,
            body_hash=body_hash,
        )
        if early is not None:
            return early
        assert record is not None
        response = handler()
        return complete_idempotent_request(record, response)
