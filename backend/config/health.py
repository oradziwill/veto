from __future__ import annotations

import logging

from django.db import connection
from django.http import HttpRequest, JsonResponse

logger = logging.getLogger(__name__)


def health(_request: HttpRequest) -> JsonResponse:
    """Process-only liveness: no database."""
    return JsonResponse({"ok": True})


def health_ready(_request: HttpRequest) -> JsonResponse:
    """
    Readiness: verify database connectivity (e.g. k8s / load-balancer probes).
    """
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        logger.exception("health_ready database check failed")
        return JsonResponse(
            {"ok": False, "checks": {"database": False}},
            status=503,
        )
    return JsonResponse({"ok": True, "checks": {"database": True}})
