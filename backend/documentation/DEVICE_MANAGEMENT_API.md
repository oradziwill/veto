# Device Management API (LAB + FISCAL)

Ten dokument opisuje kontrakty API dla warstwy Device Management:

- rejestracja i heartbeat lokalnego agenta,
- inwentaryzacja urządzeń (LAB/FISCAL),
- pobieranie komend cloud -> edge i raportowanie wyników,
- kolejka fiskalna z idempotencją i retry.

## Endpointy agentowe

### POST `/api/device-management/agents/register/`

Rejestruje (lub aktualizuje) węzeł agenta dla kliniki.

Request:

```json
{
  "clinic_id": 1,
  "node_id": "lab-connector-node",
  "name": "Lab Connector Node",
  "version": "0.1.0",
  "host": "192.168.1.40",
  "metadata": {
    "component": "lab_connector"
  }
}
```

### POST `/api/device-management/agents/heartbeat/`

Heartbeat agenta + payload diagnostyczny.

Request:

```json
{
  "clinic_id": 1,
  "node_id": "lab-connector-node",
  "status": "online",
  "host": "192.168.1.40",
  "payload": {
    "discovered_devices": 2
  }
}
```

### POST `/api/device-management/devices/upsert/`

Batch upsert inventory urządzeń wykrytych lokalnie.

Request:

```json
{
  "clinic_id": 1,
  "node_id": "lab-connector-node",
  "devices": [
    {
      "external_ref": "lab-mllp-0.0.0.0:2575",
      "device_type": "lab",
      "lifecycle_state": "active",
      "name": "Lab MLLP Listener",
      "vendor": "VETO",
      "model": "HL7 MLLP Bridge",
      "serial_number": "",
      "connection_type": "tcp_server",
      "connection_config": {
        "host": "0.0.0.0",
        "port": 2575
      },
      "capabilities": ["hl7_mllp_server", "lab_ingest"],
      "is_active": true
    }
  ]
}
```

### GET `/api/device-management/agent/commands/?node_id=<node>&clinic_id=<id>`

Pobiera oczekujące komendy dla agenta.

### POST `/api/device-management/agent/commands/{id}/result/`

Zapisuje wynik wykonania komendy.

Request:

```json
{
  "status": "succeeded",
  "result_payload": {
    "message": "Mock print successful",
    "fiscal_number": "MOCK-1234abcd"
  },
  "error_message": ""
}
```

## Endpointy aplikacji (admin / staff)

### GET `/api/device-management/devices/`

Lista urządzeń. Filtry:

- `device_type=lab|fiscal`
- `lifecycle_state=discovered|confirmed|active|offline`

### GET/POST `/api/device-management/device-events/`

- `GET` lista eventów diagnostycznych,
- `POST` zapis eventu (agent lub operator).

### GET/POST `/api/device-management/commands/`

Panel administracyjny do podglądu i tworzenia komend.

### GET/POST `/api/fiscal/receipts/`

Tworzy/parsuje zlecenia fiskalne.

- `POST` automatycznie tworzy `DeviceCommand` typu `fiscal_print`.
- Każdy rekord ma `idempotency_key`.

### POST `/api/fiscal/receipts/{id}/retry/`

Ponawia wydruk fiskalny:

- tworzy nową komendę `fiscal_print`,
- zachowuje ten sam `idempotency_key` paragonu,
- historię prób zapisuje w `FiscalReceiptPrintAttempt`.

## Kluczowe zasady

- Brak duplikacji wydruków: agent przechowuje lokalnie `processed_commands`.
- Retry nie drukuje „w ciemno” nowego paragonu, tylko raportuje po tej samej ścieżce idempotencyjnej.
- Driver ELZAB jest oddzielony adapterem; implementacja komend fiskalnych zależy od oficjalnego protokołu.
