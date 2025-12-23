# Patient Visit History – Frontend API Notes

## Overview

This document describes the **Patient Visit History** functionality added on the backend.
It enables vets to view and add medical visit notes for pets.

A **Patient History Entry** represents a medical note created by a vet for a specific pet,
optionally linked to an appointment.

---

## API Endpoints

### 1. Fetch patient visit history

GET  
`/api/patients/{patient_id}/history/`

**Example**

```
GET /api/patients/4/history/
```

**Response**

```json
[
  {
    "id": 1,
    "patient": 4,
    "clinic": 2,
    "appointment": 5,
    "visit_date": "2025-12-22T21:00:00Z",
    "note": "Follow-up: appetite improved. Continue diet for 3 days.",
    "receipt_summary": "Consultation + antiemetic",
    "created_by": 1,
    "created_by_name": "John Smith",
    "created_at": "2025-12-23T12:08:18Z"
  }
]
```

---

### 2. Create a patient visit history entry

POST  
`/api/patients/{patient_id}/history/`

**Payload**

```json
{
  "note": "Follow-up: appetite improved. Continue diet for 3 days.",
  "receipt_summary": "Consultation + antiemetic",
  "appointment": 5
}
```

**Rules**

- `note` is required
- `receipt_summary` is optional
- `appointment` must belong to:
  - the same patient
  - the same clinic
- Only vets can create entries

---

## Related endpoint

Fetch patient appointments:

```
GET /api/appointments/?patient={patient_id}
```

---

## Suggested UI Flow

1. Open patient profile
2. Load visit history
3. Load appointments
4. Select appointment
5. Add note + receipt
6. Submit and refresh list

---

## Current Limitations

- No edit/delete yet
- No attachments
- Vet-only access

---

## Status

Backend implementation complete.
Ready for frontend integration.
