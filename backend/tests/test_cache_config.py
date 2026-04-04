import pytest
from config.caches import get_caches_config


def test_cache_uses_locmem_without_redis_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("DJANGO_REDIS_URL", raising=False)
    cfg = get_caches_config()
    assert cfg["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache"


def test_cache_uses_redis_when_redis_url_set(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/2")
    monkeypatch.delenv("DJANGO_REDIS_URL", raising=False)
    cfg = get_caches_config()
    assert cfg["default"]["BACKEND"] == "django.core.cache.backends.redis.RedisCache"
    assert cfg["default"]["LOCATION"] == "redis://127.0.0.1:6379/2"
    assert cfg["default"]["KEY_PREFIX"] == "veto"
    assert cfg["default"]["OPTIONS"]["socket_connect_timeout"] == 5


def test_django_redis_url_alias(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("DJANGO_REDIS_URL", "redis://localhost:6380/0")
    cfg = get_caches_config()
    assert cfg["default"]["LOCATION"] == "redis://localhost:6380/0"


def test_redis_url_takes_precedence_over_django_alias(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://a:6379/1")
    monkeypatch.setenv("DJANGO_REDIS_URL", "redis://b:6379/1")
    assert get_caches_config()["default"]["LOCATION"] == "redis://a:6379/1"


@pytest.mark.parametrize(
    "raw,prefix",
    [
        ("prod", "prod"),
        ("  staging  ", "staging"),
    ],
)
def test_redis_key_prefix(monkeypatch, raw, prefix):
    monkeypatch.setenv("REDIS_URL", "redis://x/0")
    monkeypatch.setenv("REDIS_CACHE_KEY_PREFIX", raw)
    assert get_caches_config()["default"]["KEY_PREFIX"] == prefix


def test_redis_connect_timeout_env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://x/0")
    monkeypatch.setenv("REDIS_SOCKET_CONNECT_TIMEOUT", "12")
    assert get_caches_config()["default"]["OPTIONS"]["socket_connect_timeout"] == 12
