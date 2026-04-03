# Drug catalog (vademecum) — models, API, sync

## Overview

The **drug catalog** is a **global** (not clinic-scoped) reference layer for veterinary medicinal products. Clinics **map** their own [`InventoryItem`](../apps/inventory/models.py) rows to catalog entries and optionally link prescriptions to a catalog product for richer UI and consistency.

- **Reference data:** `ReferenceProduct` — one row per external or manual product id.
- **Operational (per clinic):** `ClinicProductMapping` — links `clinic` + optional `inventory_item` + `reference_product`, with optional alias/notes.
- **Prescriptions:** optional `Prescription.reference_product` — `drug_name` / `dosage` remain the source of truth for display; catalog is additive.

**Permissions:** all catalog endpoints require authenticated users with a clinic (`HasClinic`) and staff/vet access (`IsStaffOrVet`), same pattern as inventory.

---

## Environment variables (EMA UPD sync)

| Variable | Required | Description |
|----------|----------|-------------|
| `EMA_UPD_BASE_URL` | No | Base URL for the EMA Union Product Database read API (no trailing slash enforced in code). If unset, `sync_drug_catalog` completes successfully with **0** rows and logs a warning. |
| `EMA_UPD_API_TOKEN` | Depends on EMA | Bearer token if the API requires OAuth/client credentials. |
| `EMA_UPD_TIMEOUT_SEC` | No | HTTP timeout in seconds (default `60`). |
| `EMA_UPD_PRODUCTS_PATH` | No | Relative path under the base URL for listing products (e.g. versioned REST path). If unset, `iter_product_candidates()` returns an **empty** list — no remote HTTP for listing. |

**Note:** EMA’s public documentation should be consulted for **registration**, **rate limits**, and **response schema**. The read-only API may **not** include full SPC/leaflet documents; the client in `apps/drug_catalog/services/ema_upd.py` is a **skeleton** — extend `normalize_remote_row` in `services/sync.py` when the real JSON shape is fixed.

---

## Models (app `drug_catalog`)

### `ReferenceProduct`

| Field | Description |
|-------|-------------|
| `external_source` | `ema_upd` or `manual`. |
| `external_id` | Stable string id from source or generated for manual rows. **Unique together with `external_source`.** |
| `name`, `common_name` | Display and search. |
| `payload` | JSON blob for species, routes, regulatory fields, etc. |
| `last_synced_at`, `source_hash` | Sync metadata. |

### `SyncRun`

Log entry for each `sync_drug_catalog` run: `status`, `mode` (`full` / `incremental`), `records_processed`, `error_message`, `detail` (JSON).

### `ClinicProductMapping`

| Field | Description |
|-------|-------------|
| `clinic` | Owning clinic. |
| `inventory_item` | Optional FK to [`InventoryItem`](../apps/inventory/models.py). |
| `reference_product` | Required FK to `ReferenceProduct`. |
| `local_alias`, `is_preferred`, `notes` | Clinic-specific hints. |

**Constraints:**

- At most one mapping per `(clinic, inventory_item)` when `inventory_item` is set.
- At most one mapping per `(clinic, reference_product)` when `inventory_item` is **null** (single “alias-only” row per product per clinic).

---

## HTTP API

Base path: `/api/` (same JWT as other staff endpoints).

### Search (autocomplete / browse)

`GET /api/drug-catalog/search/`

| Query | Description |
|-------|-------------|
| `q` | Substring match on `name` or `common_name` (case-insensitive). |
| `species` | Substring match on JSON `payload` cast to text (simple filter; not a structured species taxonomy yet). |
| `limit` / `offset` | Pagination (`LimitOffsetPagination`; default limit 30, max 100). |

**Response:** Paginated list of light objects: `id`, `external_source`, `external_id`, `name`, `common_name`.

### Create manual product (API)

`POST /api/drug-catalog/products/`

Creates a **`manual`** catalog row (`external_source` is always `manual`). **Only doctors and clinic admins** (`IsDoctorOrAdmin`) — same rule as creating prescriptions.

**Body (JSON):**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name. |
| `common_name` | No | Optional INN / short name. |
| `payload` | No | JSON object (notes, dosing hints, etc.). Default `{}`. |
| `external_id` | No | Stable id for manual rows; must be unique among `manual` products. If omitted, server sets `manual-<uuid>`. |

**Response (201):** Same shape as **Product detail** (full `ReferenceProduct`).

Receptionists and other staff without doctor/admin role receive **403**.

### Product detail

`GET /api/drug-catalog/products/<id>/`

Returns full `ReferenceProduct` including `payload`, timestamps, `source_hash`. **There is no GET list endpoint** for all products (avoid accidental full-table download).

### Clinic mappings (CRUD)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/drug-catalog/mappings/` | List mappings for **current clinic** only. |
| POST | `/api/drug-catalog/mappings/` | Create mapping. Body: `inventory_item` (optional), `reference_product` (required), `local_alias`, `is_preferred`, `notes`. Server sets `clinic` from the user. |
| GET | `/api/drug-catalog/mappings/<id>/` | Retrieve one (must belong to clinic). |
| PATCH | `/api/drug-catalog/mappings/<id>/` | Partial update. |
| DELETE | `/api/drug-catalog/mappings/<id>/` | Delete. |

**Read serializer** includes nested `reference_product` (light), and when `inventory_item` is set: `inventory_item_name`, `inventory_sku`, `stock_on_hand` for “on shelf” context.

**Duplicate mapping:** database unique constraints; API may return **400** with a clear `non_field_errors` message.

---

## Prescriptions integration

Documented in [PRESCRIPTIONS.md](PRESCRIPTIONS.md). Summary:

- **Optional** field `reference_product` on create: integer **id** of `ReferenceProduct`.
- **Read** responses include nested `reference_product` (light shape) or `null`.
- `drug_name` and `dosage` stay **required** for new prescriptions as before.

---

## Management command

```bash
python manage.py sync_drug_catalog
python manage.py sync_drug_catalog --incremental
```

- Without `EMA_UPD_BASE_URL`: exits **0**, `SyncRun` with `records_processed=0` and `detail.skipped`.
- With base URL and `EMA_UPD_PRODUCTS_PATH` set: fetches JSON (see `ema_upd.iter_product_candidates`), upserts `ReferenceProduct` rows with `external_source=ema_upd`.

---

## Django admin

`ReferenceProduct`, `SyncRun`, and `ClinicProductMapping` are registered under the admin site for superusers.

---

## Tests

**pytest (unit/API integration):**

```bash
cd backend
pytest apps/drug_catalog/tests/test_drug_catalog.py -v
```

Covers: unauthenticated search → 401, search filter, mapping create, sync without EMA, sync with mocked rows, prescription POST with `reference_product`.

**Behave (Gherkin / BDD):** see [BEHAVE_TESTS.md](BEHAVE_TESTS.md) — `python manage.py behave --simple` (includes `features/drug_catalog.feature`).

---

## Migrations

- `apps/drug_catalog/migrations/0001_initial.py`
- `apps/medical/migrations/0013_prescription_reference_product.py`

Apply:

```bash
python manage.py migrate drug_catalog
python manage.py migrate medical
```
