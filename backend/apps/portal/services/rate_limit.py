"""
Portal auth rate limiting (Django cache counters).
"""

from __future__ import annotations

from django.core.cache import cache


def client_ip_from_request(request) -> str:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip() or "0.0.0.0"
    return (request.META.get("REMOTE_ADDR") or "").strip() or "0.0.0.0"


def rate_limit_exceeded(cache_key: str, limit: int, window_seconds: int) -> bool:
    """
    Increment counter for key; return True when over limit (caller should return 429).
    First hit creates the key with TTL window_seconds.
    """
    try:
        n = cache.incr(cache_key)
    except ValueError:
        cache.add(cache_key, 1, timeout=window_seconds)
        n = 1
    return n > limit


def portal_request_code_ip_key(ip: str) -> str:
    return f"portal:otp:req:ip:{ip}"


def portal_request_code_mailbox_key(clinic_slug: str, email: str) -> str:
    return f"portal:otp:req:mb:{clinic_slug}:{email}"


def portal_confirm_ip_key(ip: str) -> str:
    return f"portal:otp:cfm:ip:{ip}"


def portal_confirm_mailbox_key(clinic_slug: str, email: str) -> str:
    return f"portal:otp:cfm:mb:{clinic_slug}:{email}"
