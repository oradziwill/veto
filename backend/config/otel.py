"""
OpenTelemetry tracing for Django (opt-in via OTLP endpoint env vars).

Initializes only when ``OTEL_EXPORTER_OTLP_ENDPOINT`` or
``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`` is set and ``OTEL_SDK_DISABLED`` is not truthy.
"""

from __future__ import annotations

import logging
import os

_logger = logging.getLogger(__name__)
_initialized = False


def _env_truthy(key: str) -> bool:
    return os.getenv(key, "").strip().lower() in ("1", "true", "yes", "on")


def _otel_explicitly_disabled() -> bool:
    return _env_truthy("OTEL_SDK_DISABLED")


def _otel_exporter_configured() -> bool:
    ep = (
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or ""
    ).strip()
    return bool(ep)


def _response_hook(span, request, response) -> None:
    """Enrich the HTTP server span after middleware (request_id, user, clinic)."""
    if span is None or not span.is_recording():
        return
    rid = getattr(request, "request_id", None)
    if rid:
        span.set_attribute("veto.request_id", str(rid))
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        span.set_attribute("enduser.id", str(user.pk))
        cid = getattr(user, "clinic_id", None)
        if cid is not None:
            span.set_attribute("veto.clinic_id", int(cid))


def init_opentelemetry() -> None:
    """
    Configure OTLP HTTP trace export and Django instrumentation.

    Safe to call multiple times; only the first successful run takes effect.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    if _otel_explicitly_disabled():
        return
    if not _otel_exporter_configured():
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service_name = (os.getenv("OTEL_SERVICE_NAME") or "veto-backend").strip() or "veto-backend"
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    DjangoInstrumentor().instrument(response_hook=_response_hook)

    _logger.info("OpenTelemetry tracing enabled (service=%s)", service_name)


def reset_opentelemetry_for_tests() -> None:
    """Undo init flag for isolated tests (does not unregister tracer provider)."""
    global _initialized
    _initialized = False
