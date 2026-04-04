from config import otel


def test_init_opentelemetry_noop_without_exporter(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    otel.reset_opentelemetry_for_tests()
    otel.init_opentelemetry()
    otel.init_opentelemetry()


def test_init_opentelemetry_skips_when_sdk_disabled(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    otel.reset_opentelemetry_for_tests()
    otel.init_opentelemetry()
