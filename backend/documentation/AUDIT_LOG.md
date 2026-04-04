# Audit Log (Backend MVP)

This document describes the backend audit log added for clinic-critical operations.

## Objective

Provide a clinic-scoped, queryable audit trail for sensitive actions:
- visit closure and visit status transitions,
- clinic user management changes,
- reminder resend operations,
- clinical exam template create/update/delete and applying a template to a visit exam,
- client portal online bookings (book / cancel),
- CRM: client and client–clinic membership create/update/delete, patient create/update/delete,
- billing: invoice lifecycle (create, update, delete, send, KSeF submit, payment recorded), revenue summary CSV export,
- reports: scheduled export job download (in addition to job creation).

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
- `procedure_supply_template_created` / `procedure_supply_template_updated` / `procedure_supply_template_deleted` (`entity_type=procedure_supply_template`; doctor/admin; `after`/`before` includes `name`, `visit_type`, `is_active`, `line_count`)
- `portal_appointment_booked` (`entity_type=appointment`; `actor` is null; `metadata.source=portal`)
- `portal_booking_deposit_paid` (`entity_type=appointment`; `metadata.simulated=true` for dev simulation; Stripe Checkout when `metadata.simulated=false`, with `stripe_session_id` and optional `via=stripe_webhook`)
- `portal_appointment_cancelled` (`entity_type=appointment`; `actor` is null; `metadata.source=portal`)
- `client_gdpr_export_downloaded` (`entity_type=client`; clinic admin; `metadata.format=json` — owner data bundle for the current clinic)
- `client_created` / `client_updated` / `client_deleted` (`entity_type=client`; `before`/`after` name contact summary)
- `client_membership_created` / `client_membership_updated` / `client_membership_deleted` (`entity_type=client_clinic`; `client_id`, `is_active`, notes snippet)
- `patient_created` / `patient_updated` / `patient_deleted` (`entity_type=patient`; `before`/`after` name, species, owner, chip, primary vet)
- `invoice_created` / `invoice_updated` / `invoice_deleted` (`entity_type=invoice`; totals and line counts in `before`/`after`)
- `invoice_sent` (`entity_type=invoice`; draft → sent)
- `invoice_ksef_submitted` (`entity_type=invoice`; `after` includes `ksef_status`, `ksef_number` on success)
- `invoice_payment_recorded` (`entity_type=invoice`; `metadata` payment id, amount, method, resulting invoice status)
- `revenue_summary_exported_csv` (`entity_type=revenue_summary`; `entity_id` = clinic id; `metadata` date range and period mode)
- `report_export_job_downloaded` (`entity_type=report_export_job`; `metadata` report type and file name)

## Request correlation

`request_id` is captured from request context middleware (`X-Request-ID`) to correlate:
- API request,
- application logs,
- audit events.

## Notes

- Audit rows are strictly clinic-scoped.
- This MVP is append-only from API perspective (read-only endpoint).
