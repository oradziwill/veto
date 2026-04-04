# Inventory barcode (EAN / GTIN)

Backend support for **package barcodes** on [`InventoryItem`](../apps/inventory/models.py) — used when receiving stock from a wholesaler: the code printed on the box (typically **8–14 digits**, e.g. EAN-13, GTIN-14) can differ from the clinic’s internal **SKU**.

## Data model

- Field: `barcode` — `CharField(max_length=32)`, optional, blank default.
- Stored value: **digits only**, length **8–32** when set (spaces in input are stripped).
- Uniqueness: **`(clinic, barcode)`** when `barcode` is non-empty (partial unique constraint).

Internal **SKU** remains the primary human/internal code; **barcode** is the wholesale/retail identifier for scanning.

## API

### Create / update item

`POST` / `PUT` / `PATCH` [`/api/inventory/items/`](../apps/inventory/views.py)

Include optional `barcode` in the JSON body. Invalid values return **400** on the `barcode` field.

Create/update responses include read-only **`id`** plus writable fields (including normalized `barcode`).

### List + search

`GET /api/inventory/items/`

| Query param | Behaviour |
|-------------|-----------|
| `q` | Search **name**, **sku**, or **barcode** (substring match on barcode). |
| `barcode` | **Exact** match on normalized barcode (recommended after a scan). Invalid format → **400**. |

### Resolve by barcode (stock-in flow)

`GET /api/inventory/items/resolve_barcode/?code=<raw>`

- Requires JWT; scoped to clinics the user can access.
- `code` may contain spaces; it is normalized to digits only.
- **200** — body is the same shape as `GET /api/inventory/items/<id>/` (single item).
- **400** — missing/invalid `code`.
- **404** — no line with this barcode in scope.
- **409** — more than one line matches (data or scope issue; should be rare if uniqueness holds per clinic).

Typical client flow: **resolve_barcode** → read `id` → `POST /api/inventory/movements/` with `"kind": "in"`, `"item": <id>`, `"quantity": …`.

## Tests

- Pytest: [`apps/inventory/tests/test_barcode.py`](../apps/inventory/tests/test_barcode.py)
- Behave: [`features/inventory.feature`](../features/inventory.feature)

## Admin

Django admin lists and searches **`barcode`** on inventory items.
