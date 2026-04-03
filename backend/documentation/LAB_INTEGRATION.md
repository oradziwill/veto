# Integracja laboratoryjna (backend)

Ten dokument opisuje **gdzie trzymane są wyniki**, jak działa ingest oraz jak sensownie przechowywać **surowe payloady** w produkcji (w tym S3 per klinika).

## Gdzie są wyniki

| Warstwa | Model | Rola |
|--------|--------|------|
| Zlecenie | `LabOrder`, `LabOrderLine`, `LabTest` | Zamówienie badań, linie, katalog. |
| Wynik kliniczny (główny dla UI) | `LabResult` | Jedno na linię zlecenia; pola `value` / `value_numeric` (m.in. wpis ręczny, uproszczenie przy jednym parametrze). |
| Wynik szczegółowy (panele) | `LabResultComponent` | Wiele parametrów pod jednym `LabResult`; `lab_test`, wartości, flagi; opcjonalnie `source_observation`. |
| Import techniczny | `LabObservation` | Jedna obserwacja z urządzenia / komunikatu; powiązanie z `LabIngestionEnvelope`; `match_status`, kody vendora. |
| Identyfikacja próbki | `LabSample`, `LabExternalIdentifier` | Nasz kod próbki + zewnętrzne ID (np. `barcode`, accession). |
| Konfiguracja | `LabIntegrationDevice`, `LabTestCodeMap` | Urządzenie, token ingestu, mapowanie `vendor_code` → `LabTest`. |
| Surowy komunikat | `LabIngestionEnvelope` | Idempotencja, status przetwarzania, **treść surowa**: `raw_s3_bucket` + `raw_s3_key` (S3) albo `raw_body_text` / `raw_file`, plus `raw_sha256`, metadane. |

**Źródło prawdy dla lekarza w API read zlecenia:** `LabResult` + zagnieżdżone `components` (zob. serializery w `apps/labs/serializers.py`). `LabObservation` służy do audytu, ponownego przetworzenia i diagnostyki integracji.

Przepływ skrótowo: ingest → `LabIngestionEnvelope` → parsowanie JSON → `LabObservation` → dopasowanie do linii → **materializacja** → `LabResult` / `LabResultComponent`.

## API (REST)

Prefiks jak reszta API: `/api/`.

| Ścieżka | Opis |
|---------|------|
| `POST /api/lab-devices/<device_id>/ingest/` | Ingest (bez JWT); nagłówek `X-Lab-Ingest-Token` musi zgadzać się z `LabIntegrationDevice.ingest_token`. Body: JSON (UTF-8). Odpowiedź m.in. `created: true/false` (idempotencja). |
| `lab-integration-devices` | CRUD urządzeń (uprawnienia admin / zgodnie z `IsAdminOrReadOnly`). |
| `lab-samples` | Próbki + identifiers (lekarz/admin). |
| `lab-test-code-maps` | Mapowanie kodów vendora na `LabTest`. |
| `lab-ingestion-envelopes` | Lista / szczegół; `POST .../reprocess/` — ponowne przetworzenie tego samego envelope. |
| `lab-observations` | Lista (filtr `match_status`); `POST .../resolve/` z `lab_order_line_id` — ręczne przypięcie. |
| `lab-orders` | Bez zmian w ścieżce; read zwraca `lines[].result.components`. |

## Format JSON ingestu (MVP)

```json
{
  "identifiers": [
    {"scheme": "barcode", "value": "KOD-Z-ETYKIETY"}
  ],
  "observations": [
    {
      "vendor_code": "GLU",
      "value_numeric": "5.5",
      "unit": "mmol/L",
      "natural_key": "0"
    }
  ],
  "metadata": {}
}
```

- **Identyfikatory:** rozwiązanie zlecenia przez `LabExternalIdentifier` (powiązany z `LabSample`) lub `LabOrder.external_accession_number`.
- **`natural_key`:** unikalny w obrębie jednego envelope (replay tej samej wiadomości jest blokowany przez idempotencję na poziomie całego body).

## Surowe payloady: baza vs S3 (wdrożone)

Backend zapisuje surowy body ingestsu przez **boto3** (jak dokumenty / nagrania), **albo** trzyma go inline w DB — w zależności od konfiguracji.

### Zachowanie

| Priorytet odczytu przy parsowaniu / `reprocess` | Źródło |
|-------------------------------------------------|--------|
| 1 | `raw_s3_bucket` + `raw_s3_key` → `GetObject` |
| 2 | `raw_file` (lokalne `MEDIA` itd.) |
| 3 | `raw_body_text` |

Zapis przy ingestcie:

1. Jeśli skonfigurowany jest bucket (patrz niżej) **i** reguła trybu zezwala na S3 → obiekt wrzucany jest do S3, w DB zostają tylko `raw_s3_bucket`, `raw_s3_key`, `raw_sha256` (pole `raw_body_text` puste).
2. W przeciwnym razie treść jest w **`raw_body_text`** (np. dev, CI, małe payloady przy trybie `auto`).

Błąd odczytu z S3 ustawia na envelope status `error` i `error_code=E_RAW_LOAD`.

### Zmienne środowiskowe ([`config/settings.py`](../config/settings.py))

Szablon zmiennych: [`.env.example`](../../.env.example) w root repozytorium. Pierwsze uruchomienie lokalne (bez nadpisywania istniejącego `.env`):

```bash
./scripts/bootstrap-local-env.sh
```

Tworzy `.env` + `LAB_INGESTION_S3_ENABLED=false`, żeby surowce labów zostawały w DB nawet gdy później dopiszesz bucket dokumentów.

| Zmienna | Opis |
|---------|------|
| `LAB_INGESTION_S3_ENABLED` | Domyślnie włączone (`true`). Ustaw `false` / `0` / `off`, żeby **nigdy** nie używać S3 dla lab ingest (same `raw_body_text`), np. gdy w dev masz już `DOCUMENTS_DATA_S3_BUCKET`, ale nie chcesz tam wrzucać labów. |
| `LAB_INGESTION_S3_BUCKET` | Dedykowany bucket. Gdy pusty — używany jest **`DOCUMENTS_DATA_S3_BUCKET`** (współdzielony prefiks). |
| `LAB_INGESTION_S3_REGION` | Region (domyślnie jak dokumenty). |
| `LAB_INGESTION_S3_PREFIX` | Prefiks kluczy (np. `lab-ingestion`). Domyślny format klucza: `{prefix}/clinic_{clinic_id}/envelope_{envelope_id}.bin`. |
| `LAB_INGESTION_S3_MODE` | `auto` (domyślnie): S3 tylko gdy rozmiar body \> `LAB_INGESTION_RAW_INLINE_MAX_BYTES`. `always`: zawsze S3 przy dostępnym buckecie (wymaga IAM + bucketu; `manage.py check` ostrzeże przy braku bucketa). `never`: zawsze inline. |
| `LAB_INGESTION_RAW_INLINE_MAX_BYTES` | Próg dla trybu `auto` (domyślnie 512 KiB). |

Uprawnienia IAM: `s3:PutObject`, `s3:GetObject` na `arn:...:bucket/name/${LAB_INGESTION_S3_PREFIX}/*` (lub cały bucket w dev — niezalecane na prod).

SSE: upload używa **`ServerSideEncryption=AES256`**.

### Dlaczego prefiks z `clinic_id`

Oddziela dane klinik w jednym buckecie, ułatwia lifecycle i polityki IAM bez osobnego bucketa na tenantów.

### Testy / lokalnie

Bez ustawionego bucketa (i przy trybie `auto` / małych payloadach) Behave i lokalny dev pozostają na **`raw_body_text`**. Gdy w CI/dev masz bucket dokumentów, ale testy mają nie dotykać S3: **`LAB_INGESTION_S3_ENABLED=false`** (albo `LAB_INGESTION_S3_MODE=never`).

Polecenie: `python manage.py behave --simple features/lab_integration.feature` (z katalogu `backend/`).

## Wdrożenie: local / dev / prod (ten sam kod)

Ta sama aplikacja działa wszędzie; różnią się **tylko zmienne środowiskowe** i **migracje**.

| Krok | Local | Dev / staging | Production |
|------|--------|----------------|------------|
| Migracje | `python manage.py migrate` | W pipeline / ręcznie po deployu | Obowiązkowo w release (app `labs`). |
| Lab ingest API | `runserver` / Docker | Host dev + HTTPS opcjonalnie | Publiczny API host; **`ALLOWED_HOSTS`** musi zawierać domenę. |
| S3 | Zwykle brak bucketa → DB; lub `LAB_INGESTION_S3_ENABLED=false` | Bucket jak prod lub wyłączone S3 dla labów | Bucket + IAM (`PutObject` / `GetObject` na prefiks); zwykle **`LAB_INGESTION_S3_MODE=always`** lub **`auto`**. |
| AWS credentials | Profil lokalny / brak | Rola na serwisie lub klucze w sekrecie | **Tylko** rola (EC2/ECS/EKS) — bez kluczy w repozytorium. |
| Token urządzenia | `dev-ingest-secret` OK | Losowy string w DB | Silny `ingest_token`; rotacja jak hasło. |
| Weryfikacja config | `python manage.py check` | To samo w CI/deploy | To samo; przy `labs.W001` napraw bucket lub tryb. |

**Checklist przed pierwszym ruchem na środowisku:**
`migrate` → ustaw `.env` / secrets (według [`.env.example`](../../.env.example)) → `manage.py check` → jeden test ingest na staging → dopiero prod.

## Powiązane pliki

- Modele: `apps/labs/models.py`
- Pipeline: `apps/labs/services/ingestion_pipeline.py`
- S3 (upload / download): `apps/labs/services/lab_ingestion_storage.py`
- Parsowanie JSON: `apps/labs/integrations/json_payload.py`
- Widoki API: `apps/labs/integration_views.py`, `apps/labs/urls.py`
- Checki Django: `apps/labs/checks.py` (ostrzeżenie `labs.W001` przy `always` bez bucketa)
