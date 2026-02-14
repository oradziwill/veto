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

```bash
cd backend
python -m venv venv
source venv/bin/activate   # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
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

## Environment Variables

| Variable       | Required | Description                          |
|----------------|----------|--------------------------------------|
| `OPENAI_API_KEY` | No     | For AI patient summaries; omit to disable |
| `SECRET_KEY`     | No     | Uses dev default if not set          |
| `DATABASE_URL`   | No     | Uses SQLite by default               |

Create `.env` in project root or `backend/` and add variables as needed.

## API Overview

All endpoints except auth require: `Authorization: Bearer <access_token>`

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
| CRUD | `/api/clients/` | Clients. Filters: `?q=`, `?in_my_clinic=1` |
| CRUD | `/api/client-memberships/` | Client ↔ clinic memberships |

### Patients

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/patients/` | Patients. Filters: `?search=`, `?species=`, `?owner=`, `?vet=` |
| GET/POST | `/api/patients/<id>/history/` | Visit history (create: vets only) |
| GET | `/api/patients/<id>/ai-summary/` | AI summary (uses `OPENAI_API_KEY`) |

### Scheduling

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/appointments/` | Appointments. Filters: `?date=`, `?vet=`, `?patient=`, `?status=` |
| GET | `/api/availability/` | Free slots: `?date=YYYY-MM-DD&vet=<id>&slot=<minutes>` |
| GET/POST/PATCH | `/api/appointments/<id>/exam/` | Clinical exam (vet only) |
| POST | `/api/appointments/<id>/close-visit/` | Mark visit completed (vet only) |

### Medical

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/medical/records/` | Medical records (vet only) |
| CRUD | `/api/medical/history/` | Patient history entries (vet only) |

### Inventory

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/inventory/items/` | Items. Filters: `?q=`, `?category=`, `?low_stock=1` |
| CRUD | `/api/inventory/movements/` | Stock movements (in/out/adjust). Filter: `?item=` |

### Billing

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/billing/services/` | Service catalog (name, code, price) |
| CRUD | `/api/billing/invoices/` | Invoices. Filters: `?client=`, `?status=` |
| POST | `/api/billing/invoices/<id>/send/` | Mark invoice as sent |
| GET/POST | `/api/billing/invoices/<id>/payments/` | List or record payments |

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

- **`tests/behavior/`** – Behavior tests for end-to-end workflows (visit-to-invoice, role access, clinic isolation).
- **`conftest.py`** – Shared pytest fixtures (clinic, doctor, receptionist, patient, appointment, service, etc.).

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
- `documentation/CLINICAL_EXAM_DOCUMENTATION.md` – Clinical exam API
- `documentation/VISIT_CLOSE_WORKFLOW.md` – Visit close flow
- `documentation/HOW_TO_ADD_DATA.md` – Sample data and admin usage
