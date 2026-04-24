# Lab connector (MVP) — Mindray BC-60R Vet

Lokalny proces: **TCP MLLP (HL7)** → kolejka **SQLite** → **POST** JSON na istniejący endpoint Veto
`POST {VETO_BASE_URL}/api/lab-devices/{id}/ingest/` z nagłówkiem `X-Lab-Ingest-Token`.

Pełna specyfikacja i checklista z kliniki: [../backend/documentation/LAB_CONNECTOR_BC60R_MVP.md](../backend/documentation/LAB_CONNECTOR_BC60R_MVP.md).

## Uruchomienie

```bash
cd lab_connector
cp .env.example .env
# uzupełnij VETO_* oraz token
python -m pip install -r requirements.txt
python -m app.main
```

- **MLLP:** nasłuch `LISTEN_HOST:LISTEN_PORT` (domyślnie `0.0.0.0:2575`).
- **Health:** `http://127.0.0.1:8765/health`
- **Metrics:** `http://127.0.0.1:8765/metrics` (JSON counters runtime)
- **Kolejka:** plik SQLite w `OUTBOX_DB_PATH` (domyślnie `data/outbox.sqlite3`).

## Device Management Agent (opcjonalnie)

Po ustawieniu `AGENT_ENABLED=true` connector uruchomi dodatkową pętlę edge-agent:

- rejestracja i heartbeat do backendu Device Management,
- lokalny scan urządzeń (TCP/serial/USB heurystyki),
- `upsert` inventory do chmury,
- odbiór komend `device-management/agent/commands`,
- wykonanie `fiscal_print` przez `MockFiscalDriver` lub placeholder `ElzabFiscalDriver`.

Wymagane zmienne:

- `DM_BASE_URL`
- `DM_BEARER_TOKEN`
- `DM_NODE_ID`, `DM_NODE_NAME`
- `DM_CLINIC_ID` (dla kont z dostępem do wielu klinik)

## Wymagania

- Python **3.11+**
- Sieć wyjściowa z maszyny connectora do **HTTPS** API Veto.

## Testy jednostkowe

```bash
cd lab_connector
python -m pip install -r requirements.txt pytest
python -m pytest tests/ -v
```

## Zatrzymanie

`Ctrl+C` — graceful shutdown TCP + worker.

## Operacje (pre-production / production)

- Runbook: [`ops/RUNBOOK.md`](ops/RUNBOOK.md)
- Checklista go-live: [`ops/GO_LIVE_CHECKLIST.md`](ops/GO_LIVE_CHECKLIST.md)
- Szablon usługi Linux (`systemd`): [`ops/systemd/lab-connector.service`](ops/systemd/lab-connector.service)
- Szablon usługi macOS (`launchd`): [`ops/launchd/com.veto.lab-connector.plist`](ops/launchd/com.veto.lab-connector.plist)
