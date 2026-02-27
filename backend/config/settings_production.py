import os

from .settings import *  # noqa: F401, F403


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


# --- Core ---
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is required in production")

ALLOWED_HOSTS = _split_csv(os.getenv("ALLOWED_HOSTS", ""))
if not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS is required in production")

# --- Security behind ALB/EB ---
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Set to True only when HTTPS is configured on the ALB
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False").lower() == "true"
SESSION_COOKIE_SECURE = os.getenv("SECURE_SSL_REDIRECT", "False").lower() == "true"
CSRF_COOKIE_SECURE = os.getenv("SECURE_SSL_REDIRECT", "False").lower() == "true"

CSRF_TRUSTED_ORIGINS = _split_csv(os.getenv("CSRF_TRUSTED_ORIGINS", ""))

CORS_ALLOWED_ORIGINS = _split_csv(os.getenv("CORS_ALLOWED_ORIGINS", ""))

# HSTS - start ostrożnie, potem zwiększaj
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "False").lower() == "true"
)
SECURE_HSTS_PRELOAD = False

# --- Static (WhiteNoise) ---
_parent_middleware = MIDDLEWARE  # noqa: F405
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *[
        m
        for m in _parent_middleware
        if m
        not in (
            "django.middleware.security.SecurityMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",
        )
    ],
]

STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --- Database (RDS env vars) ---
RDS_HOSTNAME = os.getenv("RDS_HOSTNAME")
if not RDS_HOSTNAME:
    raise RuntimeError("RDS_HOSTNAME is required in production")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("RDS_DB_NAME", "veto"),
        "USER": os.getenv("RDS_USERNAME"),
        "PASSWORD": os.getenv("RDS_PASSWORD"),
        "HOST": RDS_HOSTNAME,
        "PORT": os.getenv("RDS_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    }
}

# --- Logging (minimum sane defaults for EB/CloudWatch) ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
