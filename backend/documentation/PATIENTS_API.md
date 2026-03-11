# Patients API

## GET /api/patients/

List patients for the authenticated user’s clinic. Read-only; supports filtering and search.

**Query parameters:**

- **search** – Optional. Case-insensitive full-text search across:
  - Patient name
  - Patient microchip number
  - Owner first name
  - Owner last name
  - Owner phone
  Examples: `?search=kowalski`, `?search=500100`, `?search=Burek`.

- **species** – Optional. Filter by species (exact match, case-insensitive).
- **owner** – Optional. Filter by owner (client) ID.
- **vet** – Optional. Filter by primary vet user ID.

**Response:** List of patient objects (clinic-scoped). Shape matches the patient read serializer (e.g. includes owner, primary_vet).

## Running tests

From the **backend** directory (with venv activated):

```bash
pytest apps/patients/tests/test_patient_search.py -v
```

Relevant tests:

- `test_search_by_owner_last_name` – search by owner last name (e.g. kowalski).
- `test_search_by_owner_first_name` – search by owner first name.
- `test_search_by_owner_phone` – search by owner phone (e.g. 500100).
- `test_search_by_patient_name` – search by patient name.
- `test_search_by_microchip_no` – search by microchip number.
- `test_search_case_insensitive` – same results for lowercase and uppercase search.
