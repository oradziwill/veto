# Audit Log (Backend MVP)

This document describes the backend audit log added for clinic-critical operations.

## Objective

Provide a clinic-scoped, queryable audit trail for sensitive actions:
- visit closure and visit status transitions,
- clinic user management changes,
- reminder resend operations,
- clinical exam template create/update/delete and applying a template to a visit exam,
- client portal online bookings (book / cancel).

## Data Model

Model: `AuditLog` (`apps/audit/models.py`)

Core fields:
- `clinic`
- `actor`
- `request_id`
- `action`
- `entity_type`
- `entity_id`
- `before` (JSON)
- `after` (JSON)
- `metadata` (JSON)
- `created_at`

## API

### List audit events

`GET /api/audit-logs/`

Permissions:
- authenticated
- user must belong to clinic
- clinic admin only

Optional filters:
- `action`
- `entity_type`
- `entity_id`
- `from=YYYY-MM-DD`
- `to=YYYY-MM-DD`

## Events currently emitted

- `visit_closed` (`entity_type=appointment`)
- `appointment_status_changed` (`entity_type=appointment`)
- `clinic_user_created` (`entity_type=user`)
- `clinic_user_updated` (`entity_type=user`)
- `clinic_user_deleted` (`entity_type=user`)
- `reminder_resend_queued` (`entity_type=reminder`)
- `clinical_exam_template_created` (`entity_type=clinical_exam_template`)
- `clinical_exam_template_updated` (`entity_type=clinical_exam_template`)
- `clinical_exam_template_deleted` (`entity_type=clinical_exam_template`)
- `clinical_exam_template_applied` (`entity_type=appointment`; `metadata` includes `template_id`, `template_name`, `clinical_exam_id`, `applied_fields`, `force`)
- `portal_appointment_booked` (`entity_type=appointment`; `actor` is null; `metadata.source=portal`)
- `portal_appointment_cancelled` (`entity_type=appointment`; `actor` is null; `metadata.source=portal`)

## Request correlation

`request_id` is captured from request context middleware (`X-Request-ID`) to correlate:
- API request,
- application logs,
- audit events.

## Notes

- Audit rows are strictly clinic-scoped.
- This MVP is append-only from API perspective (read-only endpoint).
