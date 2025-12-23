# VETO Backend – PR Handoff for Frontend
_Date: 2025-12-23_

This note documents the backend changes included in the current PR (feature/backend-core-v1). It is intended for the frontend team to integrate against the new/updated APIs.

---

## 1) Authentication (JWT)

### Obtain tokens
**POST** `/api/auth/token/`

Body:
```json
{"username":"<user>","password":"<pass>"}
```

Response:
```json
{"refresh":"...","access":"..."}
```

### Refresh access token
**POST** `/api/auth/token/refresh/`

Body:
```json
{"refresh":"<refresh_token>"}
```

### Authorization header (required for all protected endpoints)
Use:
```
Authorization: Bearer <ACCESS_TOKEN>
```

Common errors:
- `Authorization header must contain two space-delimited values` → missing `Bearer` or token empty
- `token_not_valid` / `Token is expired` → obtain a new access token (or refresh)

---

## 2) Accounts API

### Current user
**GET** `/api/me/`
Auth: required

Response fields (includes permissions flags):
- `id`, `username`, `first_name`, `last_name`
- `clinic` (nullable)
- `is_vet`
- `is_staff`
- `is_superuser`

### Vets list (dropdown)
**GET** `/api/vets/`
Auth: required

Behavior:
- Returns vets **in the current user’s clinic**.
- If user has no clinic → returns an empty list.

---

## 3) Clients API (multi-clinic memberships)

### Clients CRUD
Base: **`/api/clients/`**
Auth: required

Supports:
- `GET /api/clients/?q=<search>` (search across name/phone/email)
- Optional filter: `GET /api/clients/?in_my_clinic=1`

### Client membership management
Base: **`/api/client-memberships/`**
Auth: required

Represents relation: **Client ↔ Clinic** via membership model (e.g. `ClientClinic`), supporting:
- Multiple clinics per client
- Notes and activation flag (depending on model fields)

Safety rule:
- API forces new memberships into the current user’s clinic.

---

## 4) Patients API (pets)

Base: **`/api/patients/`**
Auth: required

Key points:
- Patients belong to a clinic (auto-set from current user’s clinic).
- On patient create/update, backend auto-creates a client↔clinic membership if missing.

### Read shape (list/retrieve)
Includes nested mini objects:
- `owner` (client mini)
- `primary_vet` (vet mini, nullable)

### Write shape (create/update)
Typical payload:
```json
{
  "owner": 2,
  "name": "Burek",
  "species": "Dog",
  "breed": "Mixed",
  "primary_vet": 1
}
```

---

## 5) Scheduling – Appointments API

Base: **`/api/appointments/`**
Auth: required

Filters:
- `?date=YYYY-MM-DD` (filters by appointment start date)
- `?vet=<id>`
- `?patient=<id>`
- `?status=<status>`

Create/update:
- Clinic is auto-set from the current user.

Validation:
- Prevents invalid ranges (`ends_at <= starts_at`).
- Prevents vet overlap in the same clinic (ignores cancelled).

---

## 6) Scheduling – Availability API (NEW)

### Endpoint
**GET** `/api/availability/?date=YYYY-MM-DD&vet=<vet_id>&slot=<minutes>`

Auth: required
Permissions: user must belong to a clinic.

Parameters:
- `date` (required): `YYYY-MM-DD`
- `vet` (optional, recommended): vet id to compute availability for a specific vet
- `slot` (optional): slot length in minutes (default 30)

Response example:
```json
{
  "date": "2025-12-23",
  "timezone": "UTC",
  "clinic_id": 2,
  "vet_id": 1,
  "slot_minutes": 30,
  "closed_reason": null,
  "workday": {"start": "...", "end": "..."},
  "work_intervals": [{"start": "...", "end": "..."}],
  "busy": [],
  "free": [{"start":"...","end":"..."}]
}
```

Notes:
- If vet working hours exist for that weekday, they override defaults.
- Otherwise defaults are used (09:00–17:00 unless changed in settings).
- `busy` are merged occupied blocks (excluding cancelled).
- `free` are discrete slot-sized intervals.

Error handling:
- Invalid date → `400 {"detail":"Invalid date. Use YYYY-MM-DD (e.g., 2025-12-23)."}`

Frontend recommended flow:
1) `GET /api/vets/` → choose vet
2) `GET /api/availability/?date=...&vet=...` → show available slots
3) Create appointment with chosen start/end

---

## 7) Vet Working Hours (NEW model)

Backend supports per-vet weekday working hours via `VetWorkingHours`.

Current behavior (MVP):
- Uses the first active interval for that weekday.
- Designed to extend later to multiple intervals/day (e.g., lunch break).

Frontend:
- No UI required yet; manage in Django admin for MVP.

---

## 8) Medical Records API (SOAP)

Base: **`/api/medical-records/`**
Auth: required

Rules:
- Only vets can create/update.
- Medical record is 1:1 with an appointment.
- On create, appointment status is set to `COMPLETED`.

Filter:
- `GET /api/medical-records/?appointment=<id>`

---

## Local testing (curl quickstart)

1) Obtain access token:
```bash
TOKENS=$(curl -s -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}')

ACCESS=$(python3 - <<'PY'
import json, os
print(json.loads(os.environ["TOKENS"])["access"])
PY
)
```

2) Call availability:
```bash
curl "http://127.0.0.1:8000/api/availability/?date=2025-12-23&vet=1" \
  -H "Authorization: Bearer $ACCESS"
```

---

## Integration assumptions
- Most endpoints are clinic-scoped (current user’s clinic).
- Users without `clinic` typically get empty lists or `400/403` depending on endpoint.
- “Vet” is a normal `User` with `is_vet=true`.
