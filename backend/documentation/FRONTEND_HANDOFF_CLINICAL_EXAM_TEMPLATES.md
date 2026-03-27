# Frontend Handoff: Clinical Exam Templates

This document describes how frontend can use clinic-scoped clinical exam templates.

## Endpoints

- `GET /api/medical/clinical-exam-templates/`
- `POST /api/medical/clinical-exam-templates/`
- `PATCH /api/medical/clinical-exam-templates/<id>/`
- `DELETE /api/medical/clinical-exam-templates/<id>/`
- `POST /api/appointments/<id>/exam/apply-template/`

## Apply Template Contract

Request:
```json
{
  "template_id": 12,
  "force": false
}
```

Behavior:
- if exam does not exist, backend creates it automatically
- with `force=false` (default), backend fills only empty fields
- with `force=true`, backend overwrites template-supported fields

Response includes:
- full `ClinicalExam` payload
- `template_meta`:
  - `template_id`
  - `template_name`
  - `applied_fields` (which fields were changed)
  - `force`

## UI Recommendations

1. Add "Template" dropdown in clinical exam panel.
2. On template apply, highlight changed fields using `applied_fields`.
3. Offer checkbox/toggle for "Overwrite existing values" mapped to `force=true`.
