# Inventory & Patient History API — Frontend Handoff

## Authentication
All endpoints require JWT authentication.

Authorization header:
Authorization: Bearer <ACCESS_TOKEN>

Refresh token:
POST /api/auth/token/refresh/

---

## Inventory Items

### List items
GET /api/inventory/items/

Query params:
- q: search by name or SKU
- category: medication | supply | food | other
- low_stock=true: only low-stock items

### Inventory item response
{
  "id": 1,
  "name": "Antibiotic A",
  "sku": "ANTIBIOTIC_A",
  "category": "medication",
  "unit": "vials",
  "stock_on_hand": 100,
  "low_stock_threshold": 50,
  "is_low_stock": false
}

### Create item
POST /api/inventory/items/

SKU is auto-normalized:
- uppercase
- spaces replaced with underscores

Duplicate SKU per clinic returns 400.

---

## Inventory Movements

### Create movement
POST /api/inventory/movements/

{
  "item": 1,
  "kind": "out",
  "quantity": 5,
  "note": "Dispensed"
}

Kinds:
- in: increment
- out: decrement
- adjust: absolute set

Rules:
- item must belong to clinic
- stock cannot go negative

---

## Inventory Ledger
GET /api/inventory/items/<id>/ledger/

Supports:
- ?limit=
- ?kind=

---

## Patient History

GET /api/patients/<id>/history/
POST /api/patients/<id>/history/

POST requires vet role.

---

## Error Handling
400: validation
401: auth
403: permission
404: not found

---

Stable and ready for frontend integration.
