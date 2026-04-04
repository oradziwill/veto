"""
Django CACHES configuration from the environment.

When REDIS_URL (or DJANGO_REDIS_URL) is set, the default cache uses Redis so
portal rate limits and other cache counters are shared across app instances.
Otherwise LocMem is used (fine for single-process local dev).
"""

from __future__ import annotations

import os


def get_caches_config() -> dict:
    redis_url = (os.environ.get("REDIS_URL") or os.environ.get("DJANGO_REDIS_URL") or "").strip()
    if redis_url:
        key_prefix = (os.environ.get("REDIS_CACHE_KEY_PREFIX") or "veto").strip() or "veto"
        connect_timeout = int(os.environ.get("REDIS_SOCKET_CONNECT_TIMEOUT", "5"))
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": redis_url,
                "KEY_PREFIX": key_prefix,
                "OPTIONS": {
                    "socket_connect_timeout": connect_timeout,
                },
            }
        }
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "veto-default-cache",
        }
    }
