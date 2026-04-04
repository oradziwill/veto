# OpenTelemetry (Django tracing)

Tracing is **opt-in**: nothing is exported until an OTLP endpoint is configured.

## Enable

Set one of:

| Variable | Description |
| -------- | ----------- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Base URL for OTLP (HTTP/protobuf). Example: `http://otel-collector:4318` — the HTTP exporter appends `/v1/traces`. |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Full traces URL (overrides path derivation). |

Optional:

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OTEL_SERVICE_NAME` | `veto-backend` | `service.name` resource attribute |
| `OTEL_SDK_DISABLED` | off | Set `true` to force-disable even if an endpoint is set |
| `OTEL_RESOURCE_ATTRIBUTES` | — | Standard SDK env; merged into resource (e.g. `deployment.environment=prod`) |

Disable locally by unsetting both endpoint variables or `OTEL_SDK_DISABLED=true`.

## What is instrumented

- **HTTP requests** via `opentelemetry-instrumentation-django` (WSGI + ASGI entrypoints call `init_opentelemetry()` before Django loads).
- Span attributes added on the response path:
  - `veto.request_id` — same as `X-Request-ID` / logs
  - `enduser.id` — staff/portal user id when authenticated
  - `veto.clinic_id` — staff user `clinic_id` when present

## Local collector

Example with Docker OpenTelemetry Collector listening on `4318` (HTTP):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
export OTEL_SERVICE_NAME=veto-backend-local
cd backend && python manage.py runserver
```

Production: point `OTEL_EXPORTER_OTLP_ENDPOINT` at your collector / APM ingest URL (see vendor docs for paths and auth headers).
