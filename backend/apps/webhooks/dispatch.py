"""
Dispatch outbound integration webhooks after audit-relevant events.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime

from django.conf import settings
from django.db import close_old_connections, transaction

from .models import WebhookDelivery, WebhookEventType, WebhookSubscription

logger = logging.getLogger(__name__)

_DISPATCHABLE_ACTIONS = frozenset(c[0] for c in WebhookEventType.choices)


def maybe_dispatch_webhooks_for_audit(
    *,
    clinic_id: int,
    action: str,
    entity_type: str,
    entity_id: str,
    after: dict,
    metadata: dict,
    actor,
) -> None:
    if action not in _DISPATCHABLE_ACTIONS:
        return
    actor_id = (
        getattr(actor, "id", None) if actor and getattr(actor, "is_authenticated", False) else None
    )
    payload = {
        "event": action,
        "clinic_id": clinic_id,
        "occurred_at": datetime.now(UTC).isoformat(),
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "data": {
            "after": after,
            "metadata": metadata,
            "actor_id": actor_id,
        },
    }
    schedule_deliveries_for_event(clinic_id, action, payload)


def schedule_deliveries_for_event(clinic_id: int, event_type: str, payload: dict) -> None:
    subs = WebhookSubscription.objects.filter(clinic_id=clinic_id, is_active=True).only(
        "id", "target_url", "secret", "event_types"
    )
    for sub in subs:
        types = sub.event_types or []
        if event_type not in types:
            continue
        delivery = WebhookDelivery.objects.create(
            subscription=sub,
            event_type=event_type,
            payload=payload,
            status=WebhookDelivery.Status.PENDING,
        )
        delivery_id = delivery.id

        def _spawn(did: int = delivery_id) -> None:
            threading.Thread(
                target=_deliver_delivery_thread_entry,
                args=(did,),
                daemon=True,
            ).start()

        if getattr(settings, "WEBHOOK_DELIVERY_USE_THREAD", True):
            transaction.on_commit(_spawn)
        else:
            # Same thread as caller (e.g. tests): do not close DB connections — that
            # breaks django-pytest / request transactions on PostgreSQL.
            try:
                _deliver_delivery(delivery_id)
            except Exception:
                logger.exception("Webhook delivery %s crashed", delivery_id)


def _deliver_delivery_thread_entry(delivery_id: int) -> None:
    close_old_connections()
    try:
        _deliver_delivery(delivery_id)
    except Exception:
        logger.exception("Webhook delivery %s crashed", delivery_id)
    finally:
        close_old_connections()


def _deliver_delivery(delivery_id: int) -> None:
    delivery = WebhookDelivery.objects.select_related("subscription").filter(pk=delivery_id).first()
    if not delivery:
        return
    sub = delivery.subscription
    body_dict = delivery.payload
    body_bytes = json.dumps(body_dict, separators=(",", ":"), default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Veto-Webhook/1.0",
    }
    secret = (sub.secret or "").strip()
    if secret:
        sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        headers["X-Veto-Webhook-Signature"] = f"sha256={sig}"

    req = urllib.request.Request(
        sub.target_url,
        data=body_bytes,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()[:2000]
            text = raw.decode("utf-8", errors="replace")
            delivery.status = WebhookDelivery.Status.DELIVERED
            delivery.http_status = resp.status
            delivery.response_body = text
            delivery.completed_at = datetime.now(UTC)
            delivery.save(
                update_fields=[
                    "status",
                    "http_status",
                    "response_body",
                    "completed_at",
                ]
            )
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read()[:2000].decode("utf-8", errors="replace")
        except Exception:
            pass
        delivery.status = WebhookDelivery.Status.FAILED
        delivery.http_status = exc.code
        delivery.response_body = err_body
        delivery.error = str(exc)[:1000]
        delivery.completed_at = datetime.now(UTC)
        delivery.save(
            update_fields=[
                "status",
                "http_status",
                "response_body",
                "error",
                "completed_at",
            ]
        )
    except Exception as exc:
        delivery.status = WebhookDelivery.Status.FAILED
        delivery.error = str(exc)[:1000]
        delivery.completed_at = datetime.now(UTC)
        delivery.save(
            update_fields=[
                "status",
                "error",
                "completed_at",
            ]
        )
