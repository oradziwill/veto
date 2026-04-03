# Behave (BDD) tests

The backend uses **[behave-django](https://behave-django.readthedocs.io/)** for Gherkin-style API scenarios. Feature files live under [`features/`](../features/).

## Run

From the **`backend`** directory, with venv activated and dependencies installed (`pip install -r requirements.txt`):

```bash
python manage.py behave --simple
```

- **`--simple`** — uses Django’s `TestCase` + transactions (fast, no live server). Suitable for **REST API** tests with `APIClient`.
- Omit `--simple` if you need **LiveServerTestCase** (browser / `base_url`); default is heavier.

Target one file:

```bash
python manage.py behave --simple features/drug_catalog.feature
```

Behave picks up [`behave.ini`](../behave.ini) (`paths = features`).

## Layout

| Path | Role |
|------|------|
| `features/*.feature` | Gherkin scenarios |
| `features/environment.py` | `django_ready` — e.g. `APIClient` on `context` |
| `features/steps/*.py` | `@given` / `@when` / `@then` step definitions |

## Current features

- **`features/drug_catalog.feature`** — drug catalog search auth, manual product create + search, receptionist forbidden on create.
- **`features/lab_integration.feature`** — lab ingest idempotency, `LabResultComponent` materialization, resolve unmatched observation. See [`LAB_INTEGRATION.md`](LAB_INTEGRATION.md).

## Settings

`behave_django` is listed in `INSTALLED_APPS` in [`config/settings.py`](../config/settings.py). If you want it **only in development**, move that line behind `DEBUG` or an env flag in your deployment.

## See also

- [Behave documentation](https://behave.readthedocs.io/)
- [behave-django usage](https://behave-django.readthedocs.io/en/stable/usage.html)
