"""
Redis Queue (RQ) configuration via environment.

Uses the same Redis as Django cache when REDIS_URL / RQ_REDIS_URL is set.
Set RQ_REPORT_EXPORT_ENQUEUE=0 to disable enqueue-on-create while keeping a worker URL.
"""

from __future__ import annotations

import os


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def rq_redis_url_explicit() -> str:
    """Non-empty when any known env provides a Redis URL for RQ/cache."""
    return (
        os.getenv("RQ_REDIS_URL") or os.getenv("REDIS_URL") or os.getenv("DJANGO_REDIS_URL") or ""
    ).strip()


def build_rq_config() -> tuple[dict, bool]:
    """
    Returns (RQ_QUEUES dict, RQ_REPORT_EXPORT_ENQUEUE).

    When no Redis URL is configured, enqueue-on-create defaults to False; the queue
    URL still defaults to localhost so `manage.py rqworker` works in local dev.
    """
    rq_url = rq_redis_url_explicit()
    queues = {
        "default": {
            "URL": rq_url or "redis://127.0.0.1:6379/15",
            "DEFAULT_TIMEOUT": 900,
        }
    }
    report_enqueue = _env_bool("RQ_REPORT_EXPORT_ENQUEUE", bool(rq_url))
    return queues, report_enqueue
