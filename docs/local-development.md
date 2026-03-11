# Local Development

## Prerequisites

- Python 3.12+ (required by `ksef2`)
- Node.js 18+
- PostgreSQL (or use SQLite for quick local runs)

---

## Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copy and edit environment variables
cp ../.env.example ../.env       # or create .env manually (see below)

python manage.py migrate
python manage.py seed_data       # optional: populate with sample data
python manage.py runserver
```

The API is available at `http://localhost:8000/api/`.

### Minimum `.env` for local development

```
DEBUG=True
SECRET_KEY=any-random-string-here
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

For PostgreSQL instead of SQLite:
```
DATABASE_URL=postgres://veto:password@localhost:5432/veto
```

---

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The app is available at `http://localhost:5173`.

Vite proxies `/api/*` to `http://localhost:8000/api/` (configured in `vite.config.js`), so no CORS issues in dev.

---

## Running Tests

```bash
cd backend
source venv/bin/activate
pytest                     # all tests
pytest apps/billing/       # one app only
pytest -k test_invoices    # filter by name
```

### Code Quality

```bash
ruff check .               # lint
ruff check . --fix         # auto-fix
black .                    # format
black --check .            # check only (used in CI)
```

---

## Default Credentials (after `seed_data`)

| Username | Password | Role |
|---|---|---|
| `drsmith` | `password123` | Doctor |
| `receptionist` | `password123` | Receptionist |

---

## Docker (optional)

```bash
docker compose up          # starts backend + frontend + postgres
```

See [DOCKER.md](../DOCKER.md) for details.
