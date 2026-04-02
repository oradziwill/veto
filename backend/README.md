# VETO Backend

REST API backend for a veterinary clinic management application. Built with Django and Django REST Framework, with JWT authentication and multi-clinic tenancy.

## Tech Stack

- **Django** 5.x–6.x
- **Django REST Framework**
- **djangorestframework-simplejwt** – JWT auth
- **django-cors-headers** – CORS for frontend
- **OpenAI** – AI summaries for patient history (optional)
- **SQLite** – default dev database
- **pytest** – testing
- **ruff** / **black** – linting and formatting

## Project Structure

```
backend/
├── config/                 # Django project config
│   ├── settings.py
│   └── urls.py
├── apps/
│   ├── accounts/           # Users, vets, auth
│   ├── clients/            # Pet owners, clinic memberships
│   ├── patients/           # Pets, visit history, AI summaries
│   ├── scheduling/         # Appointments, availability, clinical exams
│   ├── medical/            # Medical records, history entries
│   ├── inventory/          # Items and stock movements
│   ├── billing/            # Services, invoices, payments
│   ├── labs/               # Labs, lab tests, lab orders, results
│   ├── reminders/          # Reminder queue, delivery processing, reminder API
│   ├── documents/          # Document ingestion (upload → S3 → async HTML conversion)
│   └── tenancy/            # Clinics, holidays (models only)
├── documentation/          # API docs and handoffs
├── conftest.py             # Shared pytest fixtures
├── tests/behavior/         # End-to-end behavior tests
├── manage.py
├── requirements.txt
└── pyproject.toml          # Ruff, Black, pytest config
```

## Quick Start

### 1. Create virtual environment and install deps

From the **project root** (parent of `backend/`), so the venv lives next to frontend:

```bash
python3.13 -m venv .venv
source .venv/bin/activate   # or `.venv\Scripts\activate` on Windows
pip install -r backend/requirements.txt
```

If your venv has multiple Python versions and `python` doesn’t find Django, use the same interpreter pip used (e.g. **python3.13**):

```bash
.venv/bin/python3.13 backend/manage.py migrate
.venv/bin/python3.13 backend/manage.py runserver
```

### 2. Run migrations

```bash
python manage.py migrate
```

### 3. Seed sample data (optional)

```bash
python manage.py seed_data
```

Creates: 1 clinic, 3 users (doctor: `drsmith`, receptionist: `receptionist`, admin: `admin` — password: `password123`), clients, patients, appointments, inventory items, billing services.

### 4. Start the server

```bash
python manage.py runserver
```

API base URL: **http://localhost:8000/api/**

### 5. Create superuser (optional, for admin)

```bash
python manage.py createsuperuser
```

Admin: http://localhost:8000/admin/

## Feature Docs

- [Document ingestion async flow](documentation/DOCUMENT_INGESTION.md)
- [Visit recording + AI summary (frontend handoff)](documentation/VISIT_RECORDING_AI_SUMMARY.md)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | No | For AI patient summaries; omit to disable |
| `SECRET_KEY` | No | Uses dev default if not set |
| `POSTGRES_DB` | No | If set, backend uses PostgreSQL instead of SQLite |
| `POSTGRES_USER` | With `POSTGRES_DB` | PostgreSQL username |
| `POSTGRES_PASSWORD` | With `POSTGRES_DB` | PostgreSQL password |
| `POSTGRES_HOST` | No | PostgreSQL host (default `127.0.0.1`) |
| `POSTGRES_PORT` | No | PostgreSQL port (default `5432`) |
| `REMINDER_EMAIL_PROVIDER` | No | Reminder email provider (`internal` or `sendgrid`) |
| `REMINDER_SMS_PROVIDER` | No | Reminder SMS provider (`internal` or `twilio`) |
| `REMINDER_WEBHOOK_TOKEN` | No | Shared secret for reminder provider webhooks |
| `REMINDER_SENDGRID_API_KEY` | With SendGrid | SendGrid API key |
| `REMINDER_SENDGRID_FROM_EMAIL` | With SendGrid | Sender email for reminder messages |
| `REMINDER_SENDGRID_FROM_NAME` | No | Sender display name for SendGrid |
| `REMINDER_SENDGRID_WEBHOOK_SECRET` | Recommended | HMAC secret for SendGrid webhook signature |
| `REMINDER_TWILIO_ACCOUNT_SID` | With Twilio | Twilio Account SID |
| `REMINDER_TWILIO_AUTH_TOKEN` | With Twilio | Twilio auth token |
| `REMINDER_TWILIO_FROM_NUMBER` | With Twilio | Twilio sender phone number |
| `REMINDER_TWILIO_STATUS_CALLBACK_URL` | No | Optional Twilio status callback URL |
| `REMINDER_TWILIO_WEBHOOK_SECRET` | Recommended | HMAC secret for Twilio webhook signature |
| `REMINDER_PORTAL_BASE_URL` | Optional | Base URL used to generate owner self-service action links in reminders |
| `REMINDER_PORTAL_TOKEN_TTL_HOURS` | No | Expiry window for owner portal action tokens (default `72`) |

Create `.env` in project root or `backend/` and add variables as needed.

For ECS deployments, `OPENAI_API_KEY` should be injected from AWS Secrets Manager
(`veto-<env>/openai-api-key`) via Terraform (`terraform/secrets.tf` + `terraform/ecs.tf`).

## API Overview

All endpoints except auth require: `Authorization: Bearer <access_token>`

### Error Response Format

API errors use a standardized envelope:

```json
{
  "code": "validation_error",
  "message": "Validation failed.",
  "detail": "Validation failed.",
  "details": {
    "field_name": ["Error text"]
  },
  "status": 400
}
```

- `code` – stable machine-readable error code
- `message` / `detail` – human-readable message
- `details` – original DRF error payload (field errors or detail)
- `status` – HTTP status code

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/token/` | Obtain JWT (username, password) |
| POST | `/api/auth/token/refresh/` | Refresh access token |

### Accounts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/me/` | Current user (clinic, is_vet, etc.) |
| GET | `/api/vets/` | Vets in user’s clinic |

### Clients

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/clients/` | Clinic-scoped clients. Filter: `?q=` |
| CRUD | `/api/client-memberships/` | Client ↔ clinic memberships |

### Patients

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/patients/` | Patients. Filters: `?search=`, `?species=`, `?owner=`, `?vet=` |
| GET/POST | `/api/patients/<id>/history/` | Visit history (create: vets only) |
| GET/POST | `/api/patients/<id>/vaccinations/` | Patient vaccinations. Filter: `?upcoming=1` (next due date is today/future) |
| GET | `/api/patients/<id>/ai-summary/` | AI summary (uses `OPENAI_API_KEY`) |

### Scheduling

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/appointments/` | Appointments. Filters: `?date=`, `?vet=`, `?patient=`, `?status=` |
| GET | `/api/availability/` | Free slots: `?date=YYYY-MM-DD&vet=<id>&slot=<minutes>` |
| GET | `/api/schedule/capacity-insights/` | Capacity vs load analytics for vets. Params: `from`, `to`, `granularity=day|hour`, optional `vet`, optional `overload_threshold_pct` |
| GET | `/api/schedule/optimization-suggestions/` | Deterministic load-balancing suggestions (move/reassign). Params: `from`, `to`, optional `vet`, `limit`, optional `overload_threshold_pct` |
| GET/POST/PATCH | `/api/appointments/<id>/exam/` | Clinical exam (vet only) |
| POST | `/api/visits/<appointment_id>/transcribe/` | Upload audio (`multipart/form-data`, `audio` field, max 25MB) and generate transcript + structured visit notes (doctor/admin only) |
| POST | `/api/appointments/<id>/close-visit/` | Mark visit completed (vet only) |
| CRUD | `/api/hospital-stays/` | Hospital stays (Doctor/Admin only) |
| POST | `/api/hospital-stays/<id>/discharge/` | Discharge patient |

#### Scheduling Assistant (Backend MVP)

This backend-only feature helps clinic staff identify doctor overload and receive explainable, conflict-safe optimization suggestions.

- **Capacity insights endpoint** computes:
  - available minutes
  - booked minutes
  - utilization percent
  - overload windows based on configurable threshold
- **Optimization suggestions endpoint** returns ranked suggestions with:
  - `kind` (`reassign_vet` or `move_slot`)
  - current and proposed schedule context
  - human-readable `reason`
  - `impact_estimate` and `confidence`

Default behavior and guardrails:

- if `from` and `to` are omitted, window defaults to next 14 days
- max analysis range is 60 days
- suggestions are generated only from active appointment statuses (`scheduled`, `confirmed`, `checked_in`)
- all data is clinic-scoped; no cross-clinic leakage
- access: authenticated clinic staff (`doctor`, `receptionist`, `admin`)

Validation notes:

- `granularity` must be `day` or `hour`
- `overload_threshold_pct` must be numeric and is clamped to `[1, 100]`
- `limit` on suggestions is clamped to `[1, 20]`
- invalid date ranges return `400` with a clear `detail` message

Example:

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/schedule/capacity-insights/?from=2026-03-12&to=2026-03-26&granularity=day"
```

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/schedule/optimization-suggestions/?from=2026-03-12&to=2026-03-26&limit=5&overload_threshold_pct=80"
```

Sample response snippets:

```json
{
  "kind": "scheduling_capacity_insights",
  "window": {"from": "2026-03-12", "to": "2026-03-26"},
  "summary": {
    "available_minutes": 9600,
    "booked_minutes": 6420,
    "utilization_pct": 66.88,
    "overload_windows_count": 3
  }
}
```

```json
{
  "kind": "scheduling_optimization_suggestions",
  "count": 2,
  "suggestions": [
    {
      "kind": "reassign_vet",
      "reason": "Reassign to a lower-load qualified vet in the same time window.",
      "impact_estimate": {"minutes_shifted": 30, "overload_reduction_pct": 6.25}
    }
  ]
}
```

### Medical

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/medical/records/` | Medical records (vet only) |
| CRUD | `/api/medical/history/` | Patient history entries (vet only) |
| GET | `/api/prescriptions/` | Prescriptions list (clinic-scoped). Filters: `?patient=`, `?medical_record=` |
| GET/PATCH/DELETE | `/api/vaccinations/<id>/` | Vaccination record details and edits (create via patient route) |
| GET | `/api/vaccinations/?due_within_days=30&include_overdue=1` | Vaccination reminders (clinic-scoped). Default excludes overdue; set `include_overdue=1` to include them. Returns readable fields: `patient_name`, `owner_name`, `vaccine_name`, `next_due_date` |

### Inventory

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/inventory/items/` | Items. Filters: `?q=`, `?category=`, `?low_stock=1` |
| CRUD | `/api/inventory/movements/` | Stock movements (in/out/adjust). Filter: `?item=` |

### Billing

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/billing/services/` | Service catalog list (all clinic staff) |
| POST/PATCH/DELETE | `/api/billing/services/` | Service catalog write (clinic admin only) |
| CRUD | `/api/billing/invoices/` | Invoices. Filters: `?client=`, `?status=` |
| POST | `/api/billing/invoices/<id>/send/` | Mark invoice as sent |
| GET/POST | `/api/billing/invoices/<id>/payments/` | List or record payments |

### Labs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/labs/` | Labs (in-clinic, external). Filter: `?lab_type=` |
| POST/PATCH/DELETE | `/api/labs/` | Labs write (clinic admin only) |
| GET | `/api/lab-tests/` | Lab test catalog. Filter: `?lab=` |
| POST/PATCH/DELETE | `/api/lab-tests/` | Lab test write (clinic admin only) |
| GET | `/api/lab-orders/` | Lab orders list (clinic staff). Filters: `?patient=`, `?status=` |
| POST/PATCH/DELETE | `/api/lab-orders/` | Lab orders write (doctor/admin) |
| POST | `/api/lab-orders/<id>/send/` | Send order to lab |
| POST/PATCH | `/api/lab-orders/<id>/enter-result/` | Enter/update result (Doctor/Admin) |

### Reminders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reminders/` | Clinic-scoped reminder queue and delivery history. Filters: `?status=`, `?type=`, `?channel=` |
| GET | `/api/reminders/<id>/` | Reminder details |
| GET | `/api/reminders/metrics/` | Clinic-scoped reminder metrics snapshot (status/provider counts, failed last 24h, oldest queued age) |
| GET | `/api/reminders/analytics/` | Admin-only reminder delivery analytics. Filters: `?period=daily|monthly`, `?from=YYYY-MM-DD`, `?to=YYYY-MM-DD`, `?channel=`, `?provider=`, `?type=` |
| GET | `/api/reminders/experiment-attribution/` | Admin-only appointment reminder A/B attribution. Filters: `?from=YYYY-MM-DD`, `?to=YYYY-MM-DD`, `?channel=`, `?provider=`, `?minimum_sample_size=` |
| GET/POST/PATCH/DELETE | `/api/reminder-escalation-rules/` | Clinic escalation playbooks (staff read, admin write): trigger + delay + action |
| GET | `/api/reminder-escalation-executions/` | Clinic escalation execution log for audit/ops. Filter: `?status=applied|skipped` |
| GET | `/api/reminder-escalation-metrics/` | Admin-only escalation metrics for last 24h (`triggered_total`, `applied_total`, `skipped_total`, `by_rule`) |
| GET | `/api/reminder-replies/` | Staff queue of inbound reminder replies (default: unresolved only). Filter: `?action_status=` |
| POST | `/api/reminders/replies/<provider>/` | Public webhook for inbound owner replies (`YES/NO/RESCHEDULE`) with idempotent processing |
| GET/POST | `/api/reminders/portal/<token>/` | Public owner portal token preview/execute endpoint for `confirm`, `cancel`, `reschedule_request` |
| POST | `/api/reminders/<id>/resend/` | Re-queue reminder for retry (clinic admin only) |
| GET/POST/PATCH | `/api/reminder-preferences/` | Client consent/channel preferences, locale (`en/pl`), and quiet-hours settings |
| GET/POST/PATCH | `/api/reminder-provider-configs/` | Clinic-scoped reminder provider config (staff read, admin write). Validates external provider prerequisites |
| GET/POST/PATCH | `/api/reminder-templates/` | Clinic-scoped localized reminder templates (admin write, staff read) |
| POST | `/api/reminder-templates/preview/` | Preview rendered template output with context payload |
| POST | `/api/reminders/webhooks/<provider>/` | Provider callback for delivery status updates |

### Notifications

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications/` | Paginated in-app notifications for authenticated user (all unread + recently read), newest first |
| POST | `/api/notifications/<id>/read/` | Mark one notification as read |
| POST | `/api/notifications/read-all/` | Mark all unread notifications for user as read |
| GET | `/api/notifications/unread-count/` | Lightweight unread count payload: `{ "count": N }` |

## Apps and Responsibilities

| App | Purpose |
|-----|---------|
| **accounts** | Users, vets, JWT |
| **clients** | Pet owners, multi-clinic memberships |
| **patients** | Pets, visit history, AI summaries |
| **scheduling** | Appointments, availability, clinical exams, close visit |
| **medical** | Medical records, history entries |
| **inventory** | Items, stock movements, low-stock alerts |
| **billing** | Services, invoices, invoice lines, payments |
| **labs** | Labs, lab tests, lab orders, results (in-clinic + external) |
| **notifications** | In-app staff notification center and unread counters |
| **tenancy** | Clinics, holidays (no API routes) |

## User Roles (Personas)

Three clinic personas are supported:

| Role | Description | Can do |
|------|-------------|--------|
| **Doctor** | Veterinarian | Full access: clinical exams, close visits, medical records, patient history, appointments, inventory |
| **Receptionist** | Front desk | Appointments, clients, patients, inventory, availability. No clinical actions |
| **Clinic Admin** | Clinic administrator | Same as Doctor, plus Django admin access |

- **Doctor** and **Admin** can: create/update clinical exams, close visits, add patient history, access medical records
- **Receptionist** can: manage appointments, clients, patients, inventory, view availability
- All three roles require a clinic (`HasClinic`)

## Permissions

- **HasClinic** – User must belong to a clinic
- **IsDoctorOrAdmin** – Doctor or Clinic Admin (clinical actions)
- **IsStaffOrVet** – Any clinic role (doctor, receptionist, admin) – for appointments, inventory
- Data is scoped by user’s clinic; users without a clinic get empty lists or 403 where applicable

## Testing

```bash
pytest
# or: pytest tests/ apps/ -v
```

Run the same suite against PostgreSQL locally:

```bash
POSTGRES_DB=veto_test \
POSTGRES_USER=veto \
POSTGRES_PASSWORD=veto \
POSTGRES_HOST=127.0.0.1 \
POSTGRES_PORT=5432 \
pytest
```

- **`tests/behavior/`** – Behavior tests for end-to-end workflows (visit-to-invoice, role access, clinic isolation, vaccination edit flow).
- **`conftest.py`** – Shared pytest fixtures (clinic, doctor, receptionist, patient, appointment, service, etc.).
- GitHub Actions runs backend tests on both SQLite (`backend`) and PostgreSQL (`backend_postgres`) jobs for DB parity.

## Operations

- Each API response includes `X-Request-ID` for request tracing.
- Production logging includes `request_id`, `user_id`, and `clinic_id` context.
- Overdue invoice status updates are scheduled via EventBridge/ECS (`terraform/ops.tf`).
- Reminder queue can be hydrated/processed with management commands: `enqueue_reminders`, `process_reminders`, and `run_reminder_escalations`.
- Reminder delivery config: `REMINDER_EMAIL_PROVIDER`, `REMINDER_SMS_PROVIDER`, `REMINDER_WEBHOOK_TOKEN`.
- Health: `GET /health/` (liveness, no DB), `GET /health/ready/` (readiness, DB `SELECT 1`). Post-deploy CLI: `python manage.py deploy_smoke` with a real **origin** in `DEPLOY_SMOKE_BASE_URL` (e.g. `https://api.twojadomena.pl` or `http://127.0.0.1:8000`, no path suffix). Optional `DEPLOY_SMOKE_JWT` (**not** `JWP`) for `GET /api/me/`.
- After rotating `OPENAI_API_KEY` in Secrets Manager, force a new backend ECS deployment.

## Code Quality

```bash
ruff check .
black .
```

Config in `pyproject.toml`.

## Documentation

- `documentation/CHANGELOG_cleanup-and-next-steps.md` – Changes in this branch
- `documentation/FRONTEND_HANDOFF_backend-core-v1.md` – API integration guide
- `documentation/AVAILABILITY_API.md` – Availability endpoint
- `documentation/CLIENT_PORTAL_BOOKING.md` – Client portal (OTP + online booking API)
- `documentation/CLINICAL_EXAM_DOCUMENTATION.md` – Clinical exam API
- `documentation/VISIT_CLOSE_WORKFLOW.md` – Visit close flow
- `documentation/SCHEDULING_ASSISTANT.md` – Scheduling assistant backend (capacity + suggestions)
- `documentation/HOW_TO_ADD_DATA.md` – Sample data and admin usage
- `documentation/REMINDERS_ENGINE.md` – Reminder engine commands and API
