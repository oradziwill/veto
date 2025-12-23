# Backend Progress Summary – Patient History & Inventory

This document summarizes what was implemented in the current branch before opening the PR.
It is intended for both backend and frontend developers.

---

## 1. Patient Visit History (Medical Records)

### What was added
- A new **PatientHistoryEntry** model representing historical vet visits.
- Each entry can store:
  - visit date (derived from appointment)
  - clinical note
  - receipt summary
  - authoring vet
  - optional appointment link
- History entries are **clinic-scoped** and **patient-scoped**.

### API Endpoints
- `GET /api/patients/{patient_id}/history/`
- `POST /api/patients/{patient_id}/history/`

Validations:
- Appointment (if provided) must belong to the same clinic.
- Appointment must belong to the same patient.
- Only vets/staff can create entries.

---

## 2. Inventory Management

### InventoryItem
- Per-clinic stock tracking
- SKU unique per clinic
- Fields:
  - name
  - sku
  - category
  - unit
  - stock_on_hand
  - low_stock_threshold
  - created_by

### InventoryMovement
- Immutable stock ledger
- Kinds: in / out / adjust
- Automatically updates InventoryItem stock

---

## 3. Inventory API

### Items
- `GET /api/inventory/items/`
- Filters:
  - `q`
  - `category`
  - `low_stock=true`
- `POST /api/inventory/items/`
  - Clean 400 on duplicate SKU

### Movements
- `GET /api/inventory/movements/`
- `POST /api/inventory/movements/`

### Ledger
- `GET /api/inventory/items/{id}/ledger/`

---

## 4. Permissions
- Authenticated
- Clinic-scoped
- Staff or vet only

---

## 5. Status
- All endpoints tested via curl
- Inventory stock math verified
- Patient history verified
- Ready for PR

---

## Suggested Next Steps
- Dispensing inventory during appointments
- Role-based permissions
- Inventory reports
- Billing / invoices
