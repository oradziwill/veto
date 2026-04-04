import logging

from config.request_context import get_request_context

from .models import AuditLog

logger = logging.getLogger(__name__)


def log_audit_event(
    *,
    clinic_id: int | None,
    actor,
    action: str,
    entity_type: str,
    entity_id: str | int,
    before: dict | None = None,
    after: dict | None = None,
    metadata: dict | None = None,
):
    if not clinic_id:
        return None
    request_id, _user_id, _clinic_id = get_request_context()
    log = AuditLog.objects.create(
        clinic_id=clinic_id,
        actor=actor,
        request_id=request_id if request_id != "-" else "",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before=before or {},
        after=after or {},
        metadata=metadata or {},
    )
    try:
        from apps.webhooks.dispatch import maybe_dispatch_webhooks_for_audit

        maybe_dispatch_webhooks_for_audit(
            clinic_id=clinic_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            after=after or {},
            metadata=metadata or {},
            actor=actor,
        )
    except Exception:
        logger.exception("Integration webhook dispatch failed for action=%s", action)
    return log
