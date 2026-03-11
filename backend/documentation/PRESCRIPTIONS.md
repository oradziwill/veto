# Prescriptions: model and API

## Overview

Doctors and clinic admins record prescriptions during or after a visit. Each prescription links to a patient and optionally to a visit (MedicalRecord). Data is scoped to the authenticated user’s clinic.

- **List / create:** `GET` and `POST /api/patients/<id>/prescriptions/`
- **Retrieve one:** `GET /api/prescriptions/<id>/`

Only **doctors and clinic admins** can create prescriptions (`IsDoctorOrAdmin`). List and retrieve are available to clinic staff (`IsStaffOrVet`).

## Model (Prescription)

- **clinic**, **patient** – required; clinic scoping and patient link
- **medical_record** – optional; link to a visit (MedicalRecord)
- **appointment** – optional; kept for backward compatibility
- **prescribed_by** – user who created the prescription (set server-side)
- **drug_name**, **dosage** – required for new prescriptions (validated in API)
- **duration_days** – optional
- **notes** – optional
- **created_at** – set automatically

## Request / response

**POST** `/api/patients/<id>/prescriptions/` body example:

```json
{
  "drug_name": "Amoxicillin",
  "dosage": "5mg 2x daily",
  "duration_days": 7,
  "notes": "Take with food",
  "medical_record": null
}
```

**Response (201):** Full prescription object (id, clinic, patient, prescribed_by, drug_name, dosage, duration_days, notes, medical_record, appointment, created_at).

**GET** `/api/patients/<id>/prescriptions/` returns a list of prescriptions for that patient (newest first), clinic-scoped.

**GET** `/api/prescriptions/<id>/` returns a single prescription; 404 if it belongs to another clinic.

## Running tests

From the **backend** directory (with venv activated):

```bash
pytest apps/patients/tests/test_patient_prescriptions.py -v
```

Relevant tests:

- `test_patient_prescription_history_happy_path` – list returns prescriptions with drug_name, dosage, ordering
- `test_patient_prescription_create_happy_path` – doctor/admin can create; response has prescribed_by, clinic, patient
- `test_patient_prescription_create_forbidden_for_receptionist` – receptionist gets 403 on POST
- `test_prescription_retrieve_happy_path` – GET /api/prescriptions/<id>/ returns own clinic’s prescription
- `test_prescription_retrieve_404_other_clinic` – GET other clinic’s prescription returns 404

## Migration

New fields are added in `apps/medical/migrations/0007_prescription_drug_fields.py`. Apply with:

```bash
python manage.py migrate medical
```
