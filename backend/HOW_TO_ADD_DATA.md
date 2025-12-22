# How to Add Data to the API

There are several ways to add data to your Django API:

## Method 1: Using the Seed Command (Recommended for Initial Setup)

I've created a management command that populates the database with sample data:

```bash
cd backend
./venv/bin/python manage.py seed_data
```

This command creates:
- 1 Clinic (Veto Clinic)
- 1 Vet user (username: `drsmith`, password: `password123`)
- 3 Clients (John Doe, Jane Smith, Mike Johnson)
- 3 Patients (Max, Luna, Bunny)
- 3 Appointments
- 4 Inventory items

**Note:** The command is idempotent - it won't create duplicates if you run it multiple times.

## Method 2: Using Django Admin Interface

1. Create a superuser:
   ```bash
   cd backend
   ./venv/bin/python manage.py createsuperuser
   ```

2. Start the Django server:
   ```bash
   ./venv/bin/python manage.py runserver
   ```

3. Go to `http://localhost:8000/admin/` and log in

4. You can add/edit/delete:
   - Clinics
   - Users
   - Clients
   - Patients
   - Appointments
   - Inventory items

## Method 3: Using the API Directly

### Authentication First

You need to get a JWT token:

```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "drsmith", "password": "password123"}'
```

This returns:
```json
{
  "access": "your_access_token",
  "refresh": "your_refresh_token"
}
```

### Create a Patient

```bash
curl -X POST http://localhost:8000/api/patients/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "owner_id": 1,
    "name": "Buddy",
    "species": "Dog",
    "breed": "Labrador",
    "sex": "Male",
    "birth_date": "2020-05-15"
  }'
```

### Create an Appointment

```bash
curl -X POST http://localhost:8000/api/appointments/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": 1,
    "vet": 1,
    "starts_at": "2025-12-22T10:00:00Z",
    "ends_at": "2025-12-22T10:30:00Z",
    "reason": "Annual Checkup",
    "status": "scheduled"
  }'
```

### Create an Inventory Item

```bash
curl -X POST http://localhost:8000/api/inventory/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bandages",
    "category": "supplies",
    "stock_quantity": 100,
    "unit": "rolls",
    "min_stock_level": 20
  }'
```

## Method 4: Using Python Shell

You can also add data programmatically:

```bash
cd backend
./venv/bin/python manage.py shell
```

Then in the shell:

```python
from apps.tenancy.models import Clinic
from apps.clients.models import Client
from apps.patients.models import Patient
from apps.accounts.models import User

# Get the clinic
clinic = Clinic.objects.first()

# Get a client
client = Client.objects.first()

# Get the vet
vet = User.objects.filter(is_vet=True).first()

# Create a new patient
patient = Patient.objects.create(
    clinic=clinic,
    owner=client,
    name="Fluffy",
    species="Cat",
    breed="Siamese",
    primary_vet=vet
)

print(f"Created patient: {patient}")
```

## Quick Start

To quickly populate your database with sample data:

```bash
cd backend
./venv/bin/python manage.py seed_data
```

This will create all the sample data matching what's shown in the frontend!
