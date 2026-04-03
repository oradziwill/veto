# Zgody na zabieg (Consent documents)

Backend moduł **podpisanej zgody właściciela** powiązanej z wizytą (`Appointment`). PDF generowany jest z zamrożonego snapshotu danych (`payload_snapshot`); po podpisie dokument jest **niezmienny** (nowa wersja = nowy rekord).

**Kod:** `apps.consents` · **Storage:** pliki na S3 (jak dokumenty kliniczne), metadane w PostgreSQL.

---

## Wymagania

| Zmienna | Opis |
|---------|------|
| `DOCUMENTS_DATA_S3_BUCKET` | Bucket S3 na PDF końcowy i PNG podpisu. **Wymagane** do `POST .../sign/` i `POST .../download-url/`. |
| `DOCUMENTS_S3_REGION` | Region (np. `eu-central-1`); domyślnie `us-east-1` w kodzie. |

**Uwaga:** `GET .../preview/` zwraca PDF **bez zapisu do S3** i działa bez skonfigurowanego bucketa (przydatne do testów treści dokumentu).

---

## Uprawnienia

Jak upload dokumentów: **JWT**, użytkownik z przypisaną kliniką (`HasClinic`), rola **staff lub wet** (`IsStaffOrVet`).

---

## Endpointy

| Method | Path | Opis |
|--------|------|------|
| POST | `/api/consent-documents/` | Utworzenie dokumentu w statusie `pending_signature`. |
| GET | `/api/consent-documents/` | Lista (clinic-scoped). Query: `appointment=<id>`. |
| GET | `/api/consent-documents/<id>/` | Szczegóły. |
| GET | `/api/consent-documents/<id>/preview/` | PDF **bez** podpisu (podgląd dla klienta). `Content-Type: application/pdf`. |
| POST | `/api/consent-documents/<id>/sign/` | Multipart: podpis PNG + hash treści. Finalizacja, upload S3, status `signed`. |
| POST | `/api/consent-documents/<id>/download-url/` | Presigned GET na finalny PDF (tylko gdy `signed`). |

---

### POST create

**Body (JSON):**

```json
{
  "appointment": 123,
  "location_label": "reception"
}
```

- `appointment` — wymagane, ID wizyty z tej samej kliniki co użytkownik.
- `location_label` — opcjonalne (np. recepcja / gabinet), max 120 znaków.

**Odpowiedź (201):** serializer z polami m.in. `id`, `status`, `content_hash`, `job_id`, `created_at`. Snapshot treści **nie** jest eksponowany w API (jest w bazie pod audyt i PDF).

---

### POST sign

**Content-Type:** `multipart/form-data`

| Pole | Wymagane | Opis |
|------|----------|------|
| `content_hash` | tak | Musi **dokładnie** odpowiadać `content_hash` z create (ochrona przed race / zmianą danych między podglądem a podpisem). |
| `signature` lub `file` | tak | Plik **PNG** (nagłówek `\x89PNG...`). |

Po sukcesie: `status=signed`, `signed_at`, `signed_by` (staff), `final_pdf_s3_key`, `signature_png_s3_key`.

---

### POST download-url

**Body:** puste lub dowolne (nieużywane). Zwraca:

```json
{
  "url": "https://...",
  "expires_in": 3600
}
```

---

## Przechowywanie w S3

Prefiks: `consents/<job_id>/`

| Klucz | Zawartość |
|-------|-----------|
| `.../final.pdf` | PDF z treścią + osadzonym podpisem PNG |
| `.../signature.png` | Surowy podpis |

`job_id` to UUID rekordu (`ConsentDocument.job_id`).

---

## PDF i hash

- Snapshot (`payload_snapshot`) budowany jest z wizyty: klinika, data wizyty, pacjent, właściciel, powód, lekarz itd.
- `content_hash` = SHA-256 kanonicznego JSON (posortowane klucze, UTF-8).
- PDF renderowany jest przez PyMuPDF (`insert_htmlbox`) — poprawne wyświetlanie polskich znaków; podpis osadzany jako PNG w HTML.

---

## Model (skrót)

- `status`: `pending_signature` | `signed`
- `document_type`: obecnie `procedure_consent` (zgoda na zabieg)
- Relacje: `clinic`, `appointment`, `patient`; `created_by`, `signed_by`

---

## Frontend (skrót integracji)

1. `POST /api/consent-documents/` → zapamiętaj `id` i `content_hash`.
2. `GET /api/consent-documents/<id>/preview/` z `responseType: 'blob'` → `URL.createObjectURL` do iframe.
3. Podpis na canvasie → `toBlob('image/png')` → `FormData`: `content_hash`, `signature` (plik).
4. `POST /api/consent-documents/<id>/sign/`
5. Po podpisie: `POST .../download-url/` i otwarcie `url` w nowej karcie lub pobranie.

Szczegóły UI (modal wizyty, i18n) — u implementacji frontu w repozytorium klienta.

---

## Testy

`pytest apps/consents/tests/test_consent_api.py` — mock S3 (`_get_s3_client`), bucket testowy przez `settings.DOCUMENTS_DATA_S3_BUCKET`.

---

## CI / `manage.py check` — typowa przyczyna błędu

Jeśli w GitHub Actions pada krok **Django system check** (`import_module` w `apps.populate`):

1. **W repozytorium musi być cały kod** aplikacji wymienionych w `INSTALLED_APPS`. Jeśli w `settings.py` jest `apps.consents` i/lub `apps.drug_catalog`, oba katalogi `backend/apps/consents/` i `backend/apps/drug_catalog/` muszą być **zacommitowane i wypushowane**. Commit samych zmian w `settings.py` bez tych folderów = `ModuleNotFoundError` na CI.
2. Pakiety mają mieć `__init__.py` w katalogu aplikacji (w projekcie dodane m.in. pod Python 3.13 w CI).

**Szybki test lokalnie (jak na CI):** z katalogu `backend`, z Pythonem 3.13:

`python manage.py check`

Migracja `medical.0013_prescription_reference_product` zależy od `drug_catalog` — jeśli ta migracja jest w repo, **nie usuwaj** `drug_catalog` z `INSTALLED_APPS` bez zmiany migracji; lepiej dodać cały moduł `drug_catalog` do repozytorium.
