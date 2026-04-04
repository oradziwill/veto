# Async Report Exports (Backend MVP)

This document describes asynchronous export jobs for operational reports.

## Goal

Avoid long synchronous API responses for large report exports by introducing:
- queued export jobs,
- status polling,
- download endpoint for completed files.

## Data Model

Model: `ReportExportJob` (`apps/reports/models.py`)

Key fields:
- `report_type`: `revenue_summary`, `reminder_analytics`, `cancellation_analytics`, `accounting_invoice_lines`
- `params` (JSON input for date filters, etc.)

### `accounting_invoice_lines`

Flat CSV for accountants: **one row per invoice line** with invoice header columns repeated.

`params`:
- `from`, `to` — invoice `created_at` date (ISO), default last 30 days through today.
- `include_drafts` — optional boolean (default `false`); if `true`, include `draft` invoices.
- `include_cancelled` — optional boolean (default `false`); if `true`, include `cancelled` invoices.

By default only **`sent`**, **`paid`**, **`overdue`** invoices are included.
- `status`: `pending`, `processing`, `completed`, `failed`
- `file_name`, `file_content`, `content_type`
- `error`, `completed_at`

## API

Base endpoints:
- `POST /api/reports/exports/` - create export job
- `GET /api/reports/exports/` - list jobs (clinic-scoped)
- `GET /api/reports/exports/<id>/` - job details
- `GET /api/reports/exports/<id>/download/` - download CSV when completed
- `POST /api/reports/exports/process-pending/` - process pending jobs (admin-triggered); response includes optional `skipped` when a job was already claimed elsewhere

Permissions:
- authenticated
- clinic membership required
- clinic admin only

## Async queue (optional)

When Redis is configured (`REDIS_URL` / `RQ_REDIS_URL`) and `RQ_REPORT_EXPORT_ENQUEUE` is not disabled, **`POST /api/reports/exports/`** pushes a job to the **RQ** `default` queue. Run a worker (`python manage.py rqworker default`); see [ASYNC_JOB_QUEUE.md](ASYNC_JOB_QUEUE.md).

If no worker is running, jobs stay `pending` and are still picked up by the options below.

## Processing options

### 1) API-triggered processing

Call:
- `POST /api/reports/exports/process-pending/`

Payload:
- `limit` (optional, default `20`, range `1..200`)

### 2) Management command

```bash
python manage.py process_report_exports --limit 100
python manage.py process_report_exports --limit 50 --clinic-id 12
```

## Notes

- Jobs are hard-scoped by `clinic_id`.
- Download endpoint returns HTTP `409` until report status is `completed`.
- This MVP stores generated CSV content in DB (`file_content`) for simplicity.
