# User Roles

## Role Definitions

| Role | `role` value | What they can do |
|---|---|---|
| **Doctor** | `doctor` | Clinical exams, close visits, medical records, view all tabs |
| **Receptionist** | `receptionist` | Schedule appointments, manage waiting room, create invoices |
| **Clinic Admin** | `admin` | Everything a doctor can do + user management |

Roles are stored on the `User` model (`apps/accounts/models.py`).

---

## How the App Routes by Role

After login, `GET /api/me/` returns `{ role, username, first_name, last_name }`.

- `doctor` or `admin` → redirected to `/doctors` → `DoctorsView`
- `receptionist` → stays on `/receptionist` → `ReceptionistView`

If a doctor navigates to `/receptionist` directly, `ReceptionistView` redirects them to `/doctors` on mount.

---

## Tabs per Role

### Receptionist (`/receptionist`)
- Calendar
- Waiting Room
- Patients
- Visits
- Billing (invoice list, create invoice, submit to KSeF)

### Doctor / Admin (`/doctors`)
- Calendar
- Waiting Room
- Active Visit (clinical exam, close visit)
- Patients
- Visits
- Inventory
- AI Assistant

---

## Creating Users

### Via Django Admin (recommended for initial setup)

```bash
cd backend
./venv/bin/python manage.py createsuperuser   # creates a Django superuser
./venv/bin/python manage.py runserver
# then open http://localhost:8000/admin/
# go to Accounts → Users → Add User
# set role, assign clinic
```

### Via Management Command (dev seed)

```bash
./venv/bin/python manage.py seed_data
```

This creates a default `drsmith` (doctor) and `receptionist` user with password `password123`.

### Via API (programmatic)

Only superusers or clinic admins can create users. There is no public registration endpoint.

```bash
curl -X POST http://localhost:8000/api/users/ \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newvet",
    "password": "securepass",
    "role": "doctor",
    "clinic": 1
  }'
```

---

## Permissions System

Defined in `apps/accounts/permissions.py`:

| Permission class | Who passes |
|---|---|
| `IsAuthenticated` | Any logged-in user |
| `HasClinic` | User has a clinic assigned |
| `IsStaffOrVet` | `receptionist`, `doctor`, or `admin` |
| `IsVetOrAdmin` | `doctor` or `admin` only |

All billing endpoints require `IsAuthenticated + HasClinic + IsStaffOrVet`.

---

## Changing a User's Role

In Django Admin: **Accounts → Users → (select user) → Role field**.

Or via shell:
```python
from apps.accounts.models import User
u = User.objects.get(username="someone")
u.role = "doctor"
u.save()
```
