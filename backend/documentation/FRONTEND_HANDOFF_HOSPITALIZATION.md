# Frontend Handoff: Hospitalization Rounds, Tasks, MAR

This document is for frontend integration of hospitalization workflow improvements.

## Why this exists

Doctors should not create extra appointments for in-patient daily care.
Use `HospitalStay` as the container, then manage:
- rounds via `notes`,
- treatment workflow via `tasks`,
- medication workflow via `medications` + `administrations`.

## Endpoints

Base entity:
- `GET /api/hospital-stays/`
- `POST /api/hospital-stays/`
- `POST /api/hospital-stays/<id>/discharge/`
- `GET /api/hospital-stays/<id>/discharge-summary/`
- `PUT /api/hospital-stays/<id>/discharge-summary/`
- `POST /api/hospital-stays/<id>/discharge-summary/finalize/`
- `GET /api/hospital-stays/<id>/discharge-summary/pdf/`
- `GET /api/hospital-stays/<id>/discharge-safety-checks/`

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

Medication orders:
- `GET /api/hospital-stays/<id>/medications/`
- `POST /api/hospital-stays/<id>/medications/`
- `PATCH /api/hospital-stays/<id>/medications/<medication_id>/`
- `DELETE /api/hospital-stays/<id>/medications/<medication_id>/`

Medication administrations:
- `GET /api/hospital-stays/<id>/medications/<medication_id>/administrations/`
- `POST /api/hospital-stays/<id>/medications/<medication_id>/administrations/`
- `PATCH /api/hospital-stays/<id>/medications/<medication_id>/administrations/<administration_id>/`

Medication due alerts:
- `GET /api/hospital-stays/<id>/medications-due/?window_minutes=30&include_overdue=1`

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

### Create medication order

Request:
```json
{
  "medication_name": "Amoxicillin",
  "dose": "25.00",
  "dose_unit": "mg",
  "route": "iv",
  "frequency_hours": 8,
  "starts_at": "2026-04-01T08:00:00Z",
  "ends_at": null,
  "instructions": "Post-op protocol",
  "is_active": true
}
```

Response fields include:
- `id`, `hospital_stay`, `medication_name`, `dose`, `dose_unit`, `route`, `frequency_hours`
- `starts_at`, `ends_at`, `instructions`, `is_active`, `created_by`, `created_by_name`

### Create medication administration

Request:
```json
{
  "scheduled_for": "2026-04-01T16:00:00Z",
  "status": "given",
  "note": "Given after meal"
}
```

Response fields include:
- `id`, `medication_order`, `scheduled_for`, `status`, `note`
- `administered_at`, `administered_by`, `administered_by_name`

Backend behavior:
- when creating/updating administration with `status=given`:
  - fills `administered_at=now` if missing
  - sets `administered_by` to current user
- when status changes from `given` to non-given:
  - clears `administered_at` and `administered_by`

### Save discharge summary

Request:
```json
{
  "diagnosis": "Post-op recovery after foreign body removal",
  "hospitalization_course": "Stable during 48h observation.",
  "procedures": "Fluid therapy, wound monitoring",
  "medications_on_discharge": [
    {
      "medication_name": "Amoxicillin",
      "dose": "25",
      "dose_unit": "mg",
      "route": "oral",
      "frequency_hours": 12,
      "instructions": "for 5 days"
    }
  ],
  "home_care_instructions": "Restricted activity for 7 days.",
  "warning_signs": "Vomiting, fever, apathy",
  "follow_up_date": "2026-04-10"
}
```

Response fields include:
- `id`, `hospital_stay`, `diagnosis`, `hospitalization_course`, `procedures`
- `medications_on_discharge`, `home_care_instructions`, `warning_signs`, `follow_up_date`
- `generated_by`, `generated_by_name`, `finalized_at`, `source`

Finalize behavior:
- `POST /discharge-summary/finalize/` works only when stay status is `discharged`
- sets `finalized_at` and `generated_by`

Discharge safety behavior:
- `GET /discharge-safety-checks/` gives FE preflight validation
- `POST /discharge/` may return `400` with:
  - `code: "discharge_safety_failed"`
  - `blocking_reasons[]`
  - `warnings[]`
- FE should render blocking reasons to the user and prevent repeated submit until fixed

PDF export behavior:
- `GET /discharge-summary/pdf/` returns binary PDF (`application/pdf`)
- response is an attachment (`Content-Disposition`) ready for print/download button
- FE should only enable "Download PDF" when summary has been saved successfully

## UI recommendations

1. Hospital stay details page with two tabs:
   - `Rounds Notes`
   - `Care Plan` (`Tasks` + `Medication`)
2. Notes tab:
   - reverse chronological timeline
   - quick add with structured vitals
3. Tasks tab:
   - status buckets (`pending`, `in_progress`, `completed`, `cancelled`)
   - quick complete action
4. Tasks:
   - on status `completed`, backend fills `completed_at/completed_by`; refresh row after PATCH.
5. MAR:
   - show active medication orders with next due time (computed in FE from `starts_at + frequency_hours`)
   - provide one-click "Given" action (PATCH administration status to `given`)
   - optionally drive MAR "Now due" panel from `/medications-due/` (server-side due calculation)
6. Discharge Summary:
   - prefill form from draft (`GET /discharge-summary/`) and let doctor edit before save
   - lock printable version when `finalized_at` is set
   - add `Download PDF` CTA that opens/saves `/discharge-summary/pdf/`
   - show "Ready to discharge" badge from `/discharge-safety-checks/`
