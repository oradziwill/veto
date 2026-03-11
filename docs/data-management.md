# Data Management

## Django Admin

The Django admin interface is available at `/admin/`. Log in with a superuser account.

### Creating a superuser

```bash
# Local
cd backend
./venv/bin/python manage.py createsuperuser

# Production (ECS)
aws ecs run-task \
  --cluster veto-cluster \
  --task-definition $(aws ecs describe-task-definition --task-definition veto-backend --query 'taskDefinition.taskDefinitionArn' --output text) \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"backend","command":["python","manage.py","createsuperuser","--noinput","--username","admin","--email","admin@example.com"]}]}'
```

### Key admin sections

| Section | URL | Use for |
|---|---|---|
| Tenancy → Clinics | `/admin/tenancy/clinic/` | Set clinic name, NIP, KSeF token |
| Auth → Users | `/admin/auth/user/` | Create users, set passwords |
| Clients → Clients | `/admin/clients/client/` | View/edit clients, set client NIP for B2B |
| Billing → Invoices | `/admin/billing/invoice/` | Inspect invoices, KSeF status |
| Billing → Services | `/admin/billing/service/` | Manage service catalog |

---

## Seeding Data

### Seed script (local development)

```bash
cd backend
./venv/bin/python manage.py shell
```

```python
from apps.tenancy.models import Clinic
from apps.clients.models import Client
from apps.patients.models import Patient
from apps.billing.models import Service

# Clinic
clinic = Clinic.objects.first()
clinic.nip = "1234567890"
clinic.save()

# Client
client = Client.objects.create(
    clinic=clinic,
    first_name="Jan",
    last_name="Kowalski",
    email="jan@example.com",
    phone="500100200",
    nip="",  # leave blank for B2C
)

# Patient
patient = Patient.objects.create(
    clinic=clinic,
    owner=client,
    name="Burek",
    species="dog",
    breed="Labrador",
)

# Service catalog
Service.objects.bulk_create([
    Service(clinic=clinic, name="Konsultacja weterynaryjna", default_price="150.00", default_vat_rate="8"),
    Service(clinic=clinic, name="Szczepienie", default_price="80.00", default_vat_rate="8"),
    Service(clinic=clinic, name="Badanie krwi", default_price="120.00", default_vat_rate="8"),
])
```

---

## API Examples

All endpoints require a Bearer token. Get one with:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")
```

### Clients

```bash
# List
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/clients/

# Create
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"first_name":"Anna","last_name":"Nowak","email":"anna@example.com","phone":"600200300"}' \
  http://localhost:8000/api/clients/
```

### Patients

```bash
# List all patients
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/patients/

# List patients for a specific owner (client id=1)
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/patients/?owner=1"

# Create
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"owner":1,"name":"Mruczek","species":"cat","breed":"Europejski"}' \
  http://localhost:8000/api/patients/
```

### Services (billing catalog)

```bash
# List
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/billing/services/

# Create
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Konsultacja","default_price":"150.00","default_vat_rate":"8"}' \
  http://localhost:8000/api/billing/services/
```

### Invoices

```bash
# List
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/billing/invoices/

# Filter by status
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/billing/invoices/?status=draft"

# Create invoice with line items
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "client": 1,
    "patient": 1,
    "status": "draft",
    "due_date": "2026-04-01",
    "currency": "PLN",
    "lines": [
      {
        "description": "Konsultacja weterynaryjna",
        "quantity": 1,
        "unit": "usł",
        "unit_price": "150.00",
        "vat_rate": "8"
      }
    ]
  }' \
  http://localhost:8000/api/billing/invoices/

# Submit to KSeF
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/billing/invoices/1/submit-ksef/

# Preview KSeF XML (debug)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/billing/invoices/1/ksef-xml/
```

### Appointments

```bash
# List
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/appointments/

# Create
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "patient": 1,
    "doctor": 2,
    "start_time": "2026-04-01T10:00:00",
    "end_time": "2026-04-01T10:30:00",
    "status": "scheduled",
    "notes": ""
  }' \
  http://localhost:8000/api/appointments/
```

---

## Backups (Production)

The database is RDS PostgreSQL. AWS automated backups retain snapshots for 7 days by default (configured in Terraform).

### Manual snapshot

```bash
aws rds create-db-snapshot \
  --db-instance-identifier veto-db \
  --db-snapshot-identifier veto-manual-$(date +%Y%m%d)
```

### Restore from snapshot

1. Create a new RDS instance from the snapshot in the AWS console
2. Update the `DATABASE_URL` secret in Secrets Manager to point to the new instance
3. Force a new ECS deployment: `aws ecs update-service --cluster veto-cluster --service veto-backend --force-new-deployment`

---

## Resetting local data

```bash
cd backend
./venv/bin/python manage.py flush --no-input   # clears all rows, keeps schema
# or drop and recreate:
./venv/bin/python manage.py migrate --run-syncdb
```
