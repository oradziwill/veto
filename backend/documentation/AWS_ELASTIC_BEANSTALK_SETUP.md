# VETO – AWS Elastic Beanstalk Integration (Step-by-Step)

This guide walks you through deploying the VETO Django backend to AWS using Elastic Beanstalk **without Docker** (platform-based deployment).

---

## Prerequisites

- AWS account
- AWS CLI installed and configured (`aws configure`)
- Python 3.11+ locally (matches EB platform)
- Git

---

## Phase 1: Prepare the Application

### Step 1.1: Add production dependencies

Add to `requirements.txt`:

```
gunicorn>=21.0
whitenoise>=6.6
psycopg[binary]>=3.1
```

- **gunicorn** – production WSGI server (EB runs this)
- **whitenoise** – serves static files without a separate web server
- **psycopg** – PostgreSQL driver for RDS

### Step 1.2: Update settings for production

Make your settings read from environment variables so EB can inject config:

1. **SECRET_KEY** – must be from env in production
2. **DEBUG** – must be `False` in production
3. **ALLOWED_HOSTS** – include EB URL and your domain
4. **DATABASES** – PostgreSQL when `DATABASE_URL` or `RDS_*` vars are set
5. **STATICFILES** – use WhiteNoise for serving static files

Create `config/settings_production.py` (or extend `settings.py` with env checks) so that:

- `SECRET_KEY = os.getenv("SECRET_KEY", "dev-default")`
- `DEBUG = os.getenv("DEBUG", "false").lower() == "true"`
- `ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")` (e.g. `veto.eu-west-1.elasticbeanstalk.com,yourdomain.com`)

### Step 1.3: Add WhiteNoise to middleware

In `config/settings.py` (or production settings), add WhiteNoise **after** `SecurityMiddleware`:

```python
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # ... rest
]
```

Set:

```python
STATIC_ROOT = BASE_DIR / "staticfiles"
```

### Step 1.4: Ensure `manage.py` and `wsgi.py` exist

- `backend/manage.py` – standard Django
- `backend/config/wsgi.py` – standard Django; EB uses this

No changes needed if they’re already there.

---

## Phase 2: Create Elastic Beanstalk Application

### Step 2.1: Install EB CLI (if needed)

```bash
pip install awsebcli
```

### Step 2.2: Initialize EB in the backend directory

```bash
cd backend
eb init
```

When prompted:

- **Region**: e.g. `eu-west-1` (Ireland) or your preferred region
- **Application name**: `veto` (or any name)
- **Platform**: `Python`
- **Platform branch**: `Python 3.11 running on 64bit Amazon Linux 2023`
- **SSH**: yes (optional, for debugging)
- **Key pair**: create or select one

This creates `.elasticbeanstalk/config.yml`.

### Step 2.3: Create an environment

```bash
eb create veto-prod
```

This will:

- Create an EC2 instance
- Set up load balancer, security groups
- Deploy your app (before RDS – DB will be added next)

First deploy may fail or show DB errors if you haven’t configured RDS yet. That’s expected.

---

## Phase 3: Add RDS PostgreSQL

### Step 3.1: Create RDS instance from AWS Console

1. Go to **RDS** → **Create database**
2. **Engine**: PostgreSQL 15 or 16
3. **Template**: Free tier (or Dev/Test)
4. **DB instance identifier**: `veto-db`
5. **Master username**: `vetoadmin` (or similar)
6. **Master password**: choose a strong password and store it safely
7. **VPC**: same as your EB environment (EB uses default VPC by default)
8. **Public access**: No (private is better for production)
9. **VPC security group**: create new or use existing; EB’s EC2 must be able to reach RDS on port 5432
10. **Database name**: `veto`

### Step 3.2: Connect RDS to EB

1. In **Elastic Beanstalk** → your environment → **Configuration**
2. Edit **Software** (or **Database** if you created DB via EB)
3. Or add environment variables manually:
   - `DATABASE_URL` or individual: `RDS_HOSTNAME`, `RDS_PORT`, `RDS_DB_NAME`, `RDS_USERNAME`, `RDS_PASSWORD`

If you created RDS separately, set:

```
RDS_HOSTNAME=<your-rds-endpoint>.eu-west-1.rds.amazonaws.com
RDS_PORT=5432
RDS_DB_NAME=veto
RDS_USERNAME=vetoadmin
RDS_PASSWORD=<your-password>
```

### Step 3.3: Update Django to use RDS

In settings, add logic to use RDS when vars are present:

```python
if os.getenv("RDS_HOSTNAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("RDS_DB_NAME", "veto"),
            "USER": os.getenv("RDS_USERNAME"),
            "PASSWORD": os.getenv("RDS_PASSWORD"),
            "HOST": os.getenv("RDS_HOSTNAME"),
            "PORT": os.getenv("RDS_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
```

### Step 3.4: Run migrations on EB

```bash
eb ssh
# then in the SSH session:
source /var/app/venv/*/bin/activate
cd /var/app/current
python manage.py migrate
python manage.py createsuperuser  # if needed
exit
```

Or add a `.platform/hooks/postdeploy` script to run migrations automatically on each deploy (see Phase 6).

---

## Phase 4: Configure environment variables

### Step 4.1: Set vars in EB

```bash
eb setenv SECRET_KEY="your-long-random-secret-key-here" \
  DEBUG=False \
  ALLOWED_HOSTS="veto.eu-west-1.elasticbeanstalk.com,.elasticbeanstalk.com"
```

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Step 4.2: Optional – use AWS Systems Manager Parameter Store

For sensitive values:

1. Store in **Parameter Store** (e.g. `/veto/prod/SECRET_KEY`)
2. Grant EB’s instance role permission to read them
3. Or inject them via `.platform/confighooks` / custom config

For the first deployment, env vars via `eb setenv` are simplest.

---

## Phase 5: Static files and CORS

### Step 5.1: Collect static files at deploy

EB runs `python manage.py collectstatic --noinput` automatically if you have `collectstatic` in your platform hooks, or you can add it to the deploy process.

Ensure `STATIC_ROOT` is set and WhiteNoise is in middleware.

### Step 5.2: CORS for frontend

When you have a frontend (e.g. on Vercel/Netlify or another domain), add that origin:

```
eb setenv CORS_ALLOWED_ORIGINS="https://your-frontend.vercel.app"
```

Or in settings, read from env:

```python
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
```

---

## Phase 6: Deploy hooks (optional but recommended)

### Step 6.1: Create `.platform` directory

In `backend/`:

```
backend/
  .platform/
    hooks/
      postdeploy/
        01_migrate.sh
```

### Step 6.2: Migration hook

Create `backend/.platform/hooks/postdeploy/01_migrate.sh`:

```bash
#!/bin/bash
set -e
source /var/app/venv/*/bin/activate
cd /var/app/current
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Make it executable:

```bash
chmod +x backend/.platform/hooks/postdeploy/01_migrate.sh
```

---

## Phase 7: Deploy and verify

### Step 7.1: Deploy

```bash
cd backend
eb deploy
```

### Step 7.2: Open the app

```bash
eb open
```

Or use the URL shown in the EB console (e.g. `https://veto-prod.eu-west-1.elasticbeanstalk.com`).

### Step 7.3: Test

- `https://<your-eb-url>/api/auth/token/` – login
- `https://<your-eb-url>/admin/` – admin (after `createsuperuser`)

---

## Phase 8: Add S3 for file storage (later)

When you need to store lab results, invoices, or other files:

1. Create an S3 bucket
2. Install `django-storages` and `boto3`
3. Configure `DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"`
4. Set `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, and IAM role for EB instances to access S3

---

## Phase 9: Add SES for email (later)

For lab results, invoices, reminders:

1. Verify your domain or email in SES
2. Install `django-ses` or use `boto3` for SES
3. Set `EMAIL_BACKEND` and SES credentials via env or IAM role

---

## Troubleshooting

| Problem | Check |
|--------|-------|
| 502 Bad Gateway | Gunicorn failing; check `eb logs` |
| 500 Internal Server Error | Django error; check `eb logs`, `DEBUG=False` hides details – temporarily set `DEBUG=True` to debug, then turn off |
| DB connection refused | RDS security group must allow EB EC2 on 5432; same VPC |
| Static files 404 | WhiteNoise in middleware, `collectstatic` run, `STATIC_ROOT` set |
| CORS errors | Add frontend origin to `CORS_ALLOWED_ORIGINS` |

### View logs

```bash
eb logs
```

---

## Quick reference commands

```bash
eb init          # First-time setup
eb create        # Create environment
eb deploy        # Deploy new version
eb open          # Open app in browser
eb ssh           # SSH into instance
eb logs          # View logs
eb setenv K=V    # Set env var
eb status        # Environment status
```
