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
- `report_type`: `revenue_summary`, `reminder_analytics`, `cancellation_analytics`
- `params` (JSON input for date filters, etc.)
- `status`: `pending`, `processing`, `completed`, `failed`
- `file_name`, `file_content`, `content_type`
- `error`, `completed_at`

## API

Base endpoints:
- `POST /api/reports/exports/` - create export job
- `GET /api/reports/exports/` - list jobs (clinic-scoped)
- `GET /api/reports/exports/<id>/` - job details
- `GET /api/reports/exports/<id>/download/` - download CSV when completed
- `POST /api/reports/exports/process-pending/` - process pending jobs (admin-triggered)

Permissions:
- authenticated
- clinic membership required
- clinic admin only

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
