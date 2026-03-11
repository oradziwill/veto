# Patient profile API (single-call patient detail)

## Overview

**Endpoint:** `GET /api/patients/<id>/profile/`

Returns everything the frontend needs for the patient detail view in one response: patient, owner, last 5 medical records, all vaccinations, next 3 upcoming appointments, and open invoices. This avoids 5+ separate requests.

**Scoping:** Clinic-scoped as always. The authenticated user must belong to a clinic (e.g. **IsStaffOrVet**); only patients in that clinic are accessible. Requesting another clinic’s patient returns **404**.

**Read-only:** GET only; no create/update/delete.

## Response shape

- **patient** – Full patient object (same shape as `GET /api/patients/<id>/`), including nested owner and primary_vet.
- **owner** – `{ id, first_name, last_name, phone, email }` (patient’s owner).
- **medical_records** – Array of the **last 5** medical records (by `created_at` desc).
- **vaccinations** – Array of **all** vaccinations for the patient, ordered by `administered_at` desc.
- **upcoming_appointments** – Array of the **next 3** upcoming appointments (`starts_at >= now`, status scheduled/confirmed/checked-in), ordered by `starts_at` asc.
- **open_invoices** – Array of invoices with `status` in `draft`, `sent`, or `overdue`.

## Implementation note

The view uses **select_related** and **prefetch_related** so that all data is loaded in a bounded number of queries (no N+1).

## Running tests

From the **backend** directory (with venv activated):

```bash
pytest apps/patients/tests/test_patient_profile.py -v
```

Relevant tests:

- `test_profile_returns_200_and_shape` – response has all keys and owner fields.
- `test_profile_medical_records_last_5` – only 5 records, newest first.
- `test_profile_vaccinations_ordered` – order by administered_at desc.
- `test_profile_upcoming_appointments_next_3` – only 3, ordered by starts_at asc.
- `test_profile_open_invoices_only` – only draft/sent/overdue.
- `test_profile_404_other_clinic` – patient in another clinic returns 404.
- `test_profile_empty_lists` – empty arrays when no related data.
