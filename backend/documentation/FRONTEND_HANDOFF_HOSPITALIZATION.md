# Frontend Handoff: Hospitalization Rounds & Tasks

This document is for frontend integration of hospitalization workflow improvements.

## Why this exists

Doctors should not create extra appointments for in-patient daily care.
Use `HospitalStay` as the container, then manage rounds via `notes` and treatment via `tasks`.

## Endpoints

Base entity:
- `GET /api/hospital-stays/`
- `POST /api/hospital-stays/`
- `POST /api/hospital-stays/<id>/discharge/`

Rounds notes:
- `GET /api/hospital-stays/<id>/notes/`
- `POST /api/hospital-stays/<id>/notes/`
- `PATCH /api/hospital-stays/<id>/notes/<note_id>/`
- `DELETE /api/hospital-stays/<id>/notes/<note_id>/`

Tasks:
- `GET /api/hospital-stays/<id>/tasks/`
- `POST /api/hospital-stays/<id>/tasks/`
- `PATCH /api/hospital-stays/<id>/tasks/<task_id>/`
- `DELETE /api/hospital-stays/<id>/tasks/<task_id>/`

Permissions:
- same as hospital stays (`doctor` and `admin`)

## Payload examples

### Create note

Request:
```json
{
  "note_type": "round",
  "note": "Patient alert, appetite improving.",
  "vitals": {
    "temp_c": 38.7,
    "hr_bpm": 112,
    "rr_rpm": 22
  }
}
```

Response fields include:
- `id`, `hospital_stay`, `note_type`, `note`, `vitals`, `created_by`, `created_by_name`, `created_at`

### Create task

Request:
```json
{
  "title": "Administer antibiotic",
  "description": "IV dose every 8h",
  "priority": "high",
  "status": "pending",
  "due_at": "2026-04-01T18:00:00Z"
}
```

Response fields include:
- `id`, `hospital_stay`, `title`, `description`, `priority`, `status`, `due_at`
- `created_by`, `created_by_name`, `completed_by`, `completed_by_name`, `completed_at`

## UI recommendations

1. Hospital stay details page with two tabs:
   - `Rounds Notes`
   - `Tasks`
2. Notes tab:
   - reverse chronological timeline
   - quick add with structured vitals
3. Tasks tab:
   - status buckets (`pending`, `in_progress`, `completed`, `cancelled`)
   - quick complete action
4. On task status set to `completed`, backend fills `completed_at/completed_by`; refresh row after PATCH.
