"""
Lock out portal OTP confirm after repeated failures (per mailbox / IP).
"""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache


def _mb_block(slug: str, email: str) -> str:
    return f"portal:cblock:mb:{slug}:{email}"


def _ip_block(ip: str) -> str:
    return f"portal:cblock:ip:{ip}"


def _mb_fail(slug: str, email: str) -> str:
    return f"portal:cfail:mb:{slug}:{email}"


def _ip_fail(ip: str) -> str:
    return f"portal:cfail:ip:{ip}"


def is_portal_confirm_blocked(slug: str, email: str, ip: str) -> bool:
    if cache.get(_mb_block(slug, email)):
        return True
    if cache.get(_ip_block(ip)):
        return True
    return False


def record_portal_confirm_failure(slug: str, email: str, ip: str) -> None:
    mb_lim = int(getattr(settings, "PORTAL_CONFIRM_FAIL_LIMIT_MAILBOX", 10))
    mb_win = int(getattr(settings, "PORTAL_CONFIRM_FAIL_WINDOW_SEC", 900))
    lock_sec = int(getattr(settings, "PORTAL_CONFIRM_LOCKOUT_SEC", 900))
    ip_lim = int(getattr(settings, "PORTAL_CONFIRM_FAIL_LIMIT_IP", 40))
    ip_win = int(getattr(settings, "PORTAL_CONFIRM_FAIL_IP_WINDOW_SEC", 900))
    ip_lock = int(getattr(settings, "PORTAL_CONFIRM_LOCKOUT_IP_SEC", 1800))

    mb_key = _mb_fail(slug, email)
    try:
        n = cache.incr(mb_key)
    except ValueError:
        cache.add(mb_key, 1, timeout=mb_win)
        n = 1
    if n >= mb_lim:
        cache.set(_mb_block(slug, email), 1, timeout=lock_sec)
        cache.delete(mb_key)

    ip_key = _ip_fail(ip)
    try:
        ni = cache.incr(ip_key)
    except ValueError:
        cache.add(ip_key, 1, timeout=ip_win)
        ni = 1
    if ni >= ip_lim:
        cache.set(_ip_block(ip), 1, timeout=ip_lock)
        cache.delete(ip_key)


def clear_portal_confirm_failures(slug: str, email: str, ip: str) -> None:
    cache.delete(_mb_fail(slug, email))
    cache.delete(_ip_fail(ip))
