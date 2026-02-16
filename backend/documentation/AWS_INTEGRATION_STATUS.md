# AWS Integration – Where We Stopped

Snapshot of the AWS Elastic Beanstalk integration as of Feb 14, 2026.

---

## What’s Done

- **EB app & environment**: `veto-prod` in eu-central-1
- **Procfile**: gunicorn on port 8000
- **`.ebignore`**: venv, .env, staticfiles, db.sqlite3, etc. excluded from deploy
- **`config/settings_production.py`**: Production settings (RDS, WhiteNoise, security)
- **`config/settings.py`**: `STATIC_ROOT` added for collectstatic
- **`/health/` endpoint**: Used for EB health checks
- **`.platform/hooks/postdeploy/01_django.sh`**: Runs migrate + collectstatic on deploy
- **EB deploy**: Working with SQLite (base settings)
- **EB CLI**: Installed in backend venv (`./venv/bin/eb`)

---

## Current State

- **App URL**: https://veto-prod.eba-mwyuaee9.eu-central-1.elasticbeanstalk.com
- **Settings**: Using base `config.settings` (SQLite) because `DJANGO_SETTINGS_MODULE` is not set to `config.settings_production`
- **RDS**: Env vars configured, but database `veto` does not exist on RDS
- **ALLOWED_HOSTS**: Requests by EC2 IP `18.192.112.109` are rejected (DisallowedHost)

---

## Next Steps

1. **Create RDS database `veto`**
   - AWS RDS → Connect to instance → Create DB, or run `CREATE DATABASE veto;` as master user

2. **Use production settings and env vars**
   ```bash
   eb setenv DJANGO_SETTINGS_MODULE="config.settings_production" \
     ALLOWED_HOSTS="veto-prod.eba-mwyuaee9.eu-central-1.elasticbeanstalk.com,.elasticbeanstalk.com,18.192.112.109" \
     CSRF_TRUSTED_ORIGINS="https://veto-prod.eba-mwyuaee9.eu-central-1.elasticbeanstalk.com"
   ```
   (SECRET_KEY, RDS_HOSTNAME, RDS_DB_NAME, RDS_USERNAME, RDS_PASSWORD, DEBUG already set via eb setenv)

3. **Deploy again**
   ```bash
   cd backend && ./venv/bin/eb deploy
   ```

4. **Optional**: Add EC2 IP to ALLOWED_HOSTS if health checks or direct access via IP is needed (or rely on EB hostname only).

---

## Commands Reference

```bash
cd backend
./venv/bin/eb status
./venv/bin/eb health
./venv/bin/eb logs
./venv/bin/eb open
./venv/bin/eb setenv KEY=value
./venv/bin/eb deploy
```
