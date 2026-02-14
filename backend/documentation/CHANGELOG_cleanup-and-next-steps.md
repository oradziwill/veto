# Changelog – Branch: cleanup-and-next-steps

Summary of changes in the `cleanup-and-next-steps` branch. Intended for PR review and frontend handoff.

---

## 1. User Roles (Personas)

### What changed
- Added **3 personas**: Doctor, Receptionist, Clinic Admin.
- New `role` field on User model with choices: `doctor`, `receptionist`, `admin`.
- Migration sets existing users: `is_vet=True` → `doctor`, `is_staff=True` (non-vet) → `admin`, else → `receptionist`.

### API
- **GET `/api/me/`** – now returns `role` (doctor | receptionist | admin).

### Permissions
| Role | Can do |
|------|--------|
| **Doctor** | Clinical exams, close visit, medical records, patient history, appointments, inventory |
| **Receptionist** | Appointments, clients, patients, inventory, availability. No clinical actions |
| **Clinic Admin** | Same as Doctor + Django admin access |

### Seed data
- `drsmith` (doctor), `receptionist` (receptionist), `admin` (clinic admin) – all password: `password123`.

---

## 2. Billing Module

### New app: `apps.billing`

**Models:**
- **Service** – Catalog (name, code, price, description).
- **Invoice** – Client invoice with status (draft, sent, paid, overdue, cancelled).
- **InvoiceLine** – Line items (description, quantity, unit_price, optional service/inventory links).
- **Payment** – Payment records (amount, method, status, paid_at).

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| CRUD | `/api/billing/services/` | Service catalog |
| CRUD | `/api/billing/invoices/` | Invoices. Filters: `?client=`, `?status=` |
| POST | `/api/billing/invoices/<id>/send/` | Mark invoice as sent |
| GET/POST | `/api/billing/invoices/<id>/payments/` | List or record payments |

### Seed data
- 5 services: Consultation (150 PLN), Vaccination (80 PLN), Routine Checkup (120 PLN), Blood Test (200 PLN), X-Ray (250 PLN).

---

## 3. Behavior Tests & Fixtures

### Shared fixtures (`conftest.py`)
- `clinic`, `doctor`, `receptionist`, `clinic_admin`
- `client`, `client_with_membership`, `patient`
- `appointment`, `service`, `inventory_item`
- `api_client`

### Behavior tests (`tests/behavior/`)

| File | Coverage |
|------|----------|
| `test_visit_to_invoice_workflow.py` | Full flow: book → exam → close → invoice → pay; partial payments |
| `test_role_access.py` | Receptionist vs doctor vs admin permissions |
| `test_clinic_isolation.py` | Multi-clinic data isolation |

---

## 4. Other Changes

- **AppointmentWriteSerializer** – added read-only `id` so create response includes new appointment ID.
- **Billing tests** – refactored to use shared fixtures.
- **Clinical exam / close-visit tests** – updated to set `role=User.Role.DOCTOR` for vet users.
- **Backend README** – expanded with billing, roles, test structure, fixtures.

---

## Migration

```bash
python manage.py migrate
```

New migration: `accounts.0002_add_user_role`, `billing.0001_initial`.

---

## Test Count

22 tests total (9 behavior, 13 app tests). Run: `pytest tests/ apps/ -v`.
