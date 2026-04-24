# Lab connector MVP — Mindray BC-60R Vet (HL7/MLLP → Veto JSON)

Ten dokument zastępuje brak osobnego repo do czasu wdrożenia kodu: **specyfikacja + checklista kliniki**. Implementacja: katalog `lab_connector/` w root (Python 3.11+), patrz sekcje poniżej.

## Co już wiemy z `Instrukcje/.../BC-60R HL7 Communication Protocol.pdf`

- **MLLP:** `<0x0B>` + payload UTF-8 + `<0x1C><0x0D>`.
- **HL7 2.3.1**, charset **UNICODE** (UTF-8).
- Wyniki: **ORU^R01**; potwierdzenie: **ACK^R01** z **MSA|AA|&lt;MSH-10&gt;**.
- Segmenty wyniku: **MSH**, **[PID]**, **[PV1]**, **{ OBR { OBX* } }** (zgodnie z dokumentem).
- **Identyfikacja próbki (wynik):** **OBR-3** (*Filler Order Number*) — w przykładzie `TestSampleID1` (pole 3 segmentu OBR po `|`).
- **OBX-3:** `ID^Name^EncodeSys` (np. `6690-2^WBC^LN`) — **ID** (pierwszy komponent) jako `vendor_code` w JSON Veto.
- **OBX-5** wartość, **OBX-6** jednostki, **OBX-7** zakres referencyjny (np. `6.00-17.00` → `ref_low` / `ref_high` po split).
- **Worklist:** ORM/ORR — poza MVP samego „wyniku”; można dodać w v2.

## Kontrakt z backendem Veto (bez nowego endpointu)

Connector wysyła **HTTP POST** dokładnie na istniejący ingest:

- URL: `{VETO_BASE_URL}/api/lab-devices/{VETO_DEVICE_ID}/ingest/`
- Nagłówek: `X-Lab-Ingest-Token: {VETO_INGEST_TOKEN}`
- `Content-Type: application/json`
- Body (UTF-8) zgodny z [LAB_INTEGRATION.md](LAB_INTEGRATION.md):

```json
{
  "identifiers": [
    { "scheme": "barcode", "value": "<OBR-3 sample id>" }
  ],
  "observations": [
    {
      "vendor_code": "6690-2",
      "natural_key": "1",
      "vendor_name": "WBC",
      "value_text": "9.55",
      "value_numeric": "9.55",
      "unit": "10*9/L",
      "ref_low": "6.00",
      "ref_high": "17.00",
      "abnormal_flag": ""
    }
  ],
  "metadata": { "hl7_message_type": "ORU^R01", "connector": "lab_connector_bc60r", "version": "0.1" }
}
```

**Uwaga:** `scheme` musi odpowiadać temu, co jest w bazie (`LabExternalIdentifier`) lub użyj dopasowania po `LabOrder.external_accession_number` — patrz [identifier_resolution](../apps/labs/services/identifier_resolution.py).

## Architektura MVP (jeden proces)

1. **TCP server** (`asyncio`): nasłuch `LISTEN_HOST:LISTEN_PORT`; dla każdego połączenia bufor binarny, wycinanie ramek MLLP.
2. **Parser HL7:** minimalny split po `\r`, pola po `|`; wykrycie `ORU^R01` w MSH; wyciągnięcie pierwszego OBR + wszystkich OBX w tej samej „grupie” (MVP: jeden OBR na wiadomość).
3. **ACK:** po odebraniu (nawet przy błędzie parsowania — rozważ `MSA|AE|` przy błędzie krytycznym) odesłanie MLLP z powrotem na to samo gniazdo.
4. **Kolejka SQLite:** zapis JSON do wysłania; worker co N sekund `httpx` POST; backoff z `.env`.
5. **Health (opcjonalnie):** mały `ThreadingHTTPServer` `GET /health` → `ok`.

## Zmienne środowiskowe (`.env`)

Patrz przykład w sekcji „Przykładowy `.env.example`” — skopiuj do `lab_connector/.env` (nie commituj).

| Zmienna | Opis |
|---------|------|
| `VETO_BASE_URL` | Pełny URL API (z `https`), bez końcowego `/` |
| `VETO_DEVICE_ID` | PK `LabIntegrationDevice` w Veto |
| `VETO_INGEST_TOKEN` | Ten sam co w bazie na urządzeniu |
| `LISTEN_HOST` / `LISTEN_PORT` | Gdzie słucha LIS (np. `2575`) |
| `SAMPLE_IDENTIFIER_SCHEME` | Domyślnie `barcode` — musi zgadzać się z danymi w Veto |
| `OUTBOX_DB_PATH` | Ścieżka do pliku SQLite kolejki |
| `RETRY_BACKOFF_SEC` | Lista opóźnień retry |

## Przykładowy `.env.example` (do utworzenia obok connectora)

```
VETO_BASE_URL=https://api.example.com
VETO_DEVICE_ID=1
VETO_INGEST_TOKEN=

LISTEN_HOST=0.0.0.0
LISTEN_PORT=2575
SAMPLE_IDENTIFIER_SCHEME=barcode

OUTBOX_DB_PATH=data/outbox.sqlite3
HEALTH_HOST=127.0.0.1
HEALTH_PORT=8765
RETRY_BACKOFF_SEC=60,300,900,3600
```

## Lista: czego potrzebujemy z kliniki (żeby **jeden** BC-60R „działał” end-to-end)

1. **Stały adres IP** komputera z connectorem (lub DHCP z rezerwacją) oraz **port** wpisany w menu komunikacji analizatora / PC pośredniczącego jako **adres LIS / host**.
2. **Potwierdzenie kierunku TCP:** czy analizator (lub PC Mindray) **łączy się jako klient** do Waszego serwera connectora (typowe dla „LIS passive”) — jeśli odwrotnie, trzeba dodać tryb **outbound client** w v1.1.
3. **Jeden rzeczywisty zrzut** surowego ORU^R01 z produkcji (plik `.txt`) po pierwszym udanym teście — weryfikacja, że **OBR-3** to faktycznie ten sam numer co na etykiecie / w Veto.
4. **W Veto przed testem:** `LabIntegrationDevice` (to `device_id` + token), **zlecenie** + **próbka** z `LabExternalIdentifier` (`scheme` = np. `barcode`, `value` = ten sam co **OBR-3**) **lub** `LabOrder.external_accession_number` = OBR-3.
5. **`LabTestCodeMap`** dla BC-60R: mapowanie kodów z OBX-3 (np. `6690-2`, `789-8`, …) na `LabTest` — bez tego obserwacje będą **UNMATCHED** (wynik w systemie, ale nie na linii).
6. **Firewall:** z sieci labu do `VETO_BASE_URL` wychodzący **HTTPS** (443) do wysyłki JSON.
7. **Certyfikat / DNS** produkcyjnego API (connectorr weryfikuje TLS).

## Implementacja w repo

- Katalog: [`lab_connector/`](../../lab_connector/) — `python -m app.main` (z `lab_connector/` po `cp .env.example .env` i uzupełnieniu `VETO_*`).
- Testy: `lab_connector/tests/test_hl7.py` (`pytest`).
- `lab_connector/data/` jest w [`.gitignore`](../../.gitignore) (root).

## vetXpert Cube

Spec HL7 jest w `.doc` — narzędzia CI nie czytają binarnie; **wyeksportuj do PDF** do folderu `Instrukcje/` i powtórz ten sam schemat **osobnego** `device_id` + adaptera `mindray_vetxpert_cube`.
