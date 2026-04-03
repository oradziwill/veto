# Clinic network tenancy — helpers and Behave tests

This document describes how **multi-clinic / network** access is enforced in the backend and how we validate part of that behaviour with **Behave** (Gherkin) scenarios.

## Runtime helpers (`apps.tenancy.access`)

| Helper | When to use |
|--------|-------------|
| `accessible_clinic_ids(user)` | Querysets: `Model.objects.filter(clinic_id__in=accessible_clinic_ids(user))`. Returns all clinic PKs the user may see (single clinic, or every clinic in the network for `network_admin`, or all clinics for superuser). |
| `clinic_id_for_mutation(user, *, request, instance_clinic_id=None)` | Creates/updates that need **exactly one** `clinic_id`. If the user has more than one accessible clinic, they must pass `clinic_id` in the query string or JSON body (unless `instance_clinic_id` pins the row, e.g. updating an existing record). |
| `clinic_instance_for_mutation(user, request, *, instance_clinic_id=None)` | Same as above but returns a `Clinic` instance for `serializer.save(clinic=...)`. |
| `user_can_access_clinic(user, clinic_id)` | Permission checks and validation (e.g. “can this user touch this patient’s clinic?”). |

**Important:** `clinic_id__in=...` is valid only on **querysets** (`.filter()`). Never pass `clinic_id__in` to `Model.objects.create()`, `serializer.save()`, or similar — use a single `clinic_id=<int>` (often from the parent appointment, stay, or `clinic_id_for_mutation`).

## Behave layout

| Path | Role |
|------|------|
| `backend/features/*.feature` | Gherkin scenarios |
| `backend/features/steps/*.py` | Step definitions |
| `backend/features/environment.py` | `django_ready`: attaches `APIClient` and `context.last_response` |

Shared HTTP assertion:

- `backend/features/steps/common_steps.py` — e.g. `Then the response status is {code}` (used by multiple features).

## Running Behave locally

From `backend/` with your virtualenv activated and dependencies installed:

```bash
python manage.py behave --simple
```

Run only tenancy scenarios:

```bash
python manage.py behave features/tenancy.feature --simple
```

`--simple` uses the DRF `APIClient` (no live HTTP server), same style as existing drug catalog and lab integration features.

## Tenancy feature file

`backend/features/tenancy.feature` covers:

- Unauthenticated `GET /api/me/` → `401`.
- Network admin `GET /api/me/` → `200`, `role=network_admin`, non-null `network`.
- Single-clinic vet `GET /api/me/` → `200`, `role=doctor`, `clinic` matches the user’s clinic.
- Network admin `GET /api/vets/` → vets from **both** clinics in the network appear.
- Vet in clinic A `GET /api/vets/` → vets from clinic B in the same network do **not** appear (scoped to accessible clinics only).

These scenarios are **not** a full security audit; they document and guard the main HTTP contracts for `/api/me/` and `/api/vets/` under tenancy. Complement with unit tests (`apps/tenancy/tests_access.py`) and broader API tests as needed.

## Related code

- `apps/tenancy/access.py` — helper implementations.
- `apps/accounts/views.py` — `MeView`, `VetViewSet` (examples of `accessible_clinic_ids` on read APIs).
