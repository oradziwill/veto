"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.otel import init_opentelemetry

init_opentelemetry()

from django.core.asgi import get_asgi_application  # noqa: E402

application = get_asgi_application()
