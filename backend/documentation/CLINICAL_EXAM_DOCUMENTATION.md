# Clinical Exam & Medical Models – Developer Documentation

## Overview
This change introduces a **Clinical Exam** concept tied 1:1 to an Appointment and normalizes medical-domain models to be clinic-scoped and future-proof for prescriptions and auditability.

This document is intended for backend, frontend, and reviewers.

---

## Scope of Changes

### New Domain Object
- **ClinicalExam**
  - One-to-one with `Appointment`
  - Clinic-scoped
  - Fully optional fields (safe for incremental data entry during visit)

### Normalized Medical Models
- `MedicalRecord`
  - Now explicitly linked to `Clinic` and `Patient`
  - Retains `ai_summary` (partner-owned; unchanged)
- `PatientHistoryEntry`
  - Now linked to `MedicalRecord` instead of Appointment/Patient directly
  - Enables longitudinal patient history independent of visit structure

### New API Endpoint
- `GET /api/appointments/{id}/exam/`
- `POST /api/appointments/{id}/exam/`
- `PATCH /api/appointments/{id}/exam/`

---

## ClinicalExam Model

```python
class ClinicalExam(models.Model):
    clinic
    appointment (OneToOne)
    initial_notes
    clinical_examination

    temperature_c
    heart_rate_bpm
    respiratory_rate_rpm

    additional_notes
    owner_instructions
    initial_diagnosis

    created_by
    created_at
    updated_at
```

### Field Semantics (Vet-driven)
- **initial_notes** – free-form notes at visit start
- **clinical_examination** – assessment narrative
- **temperature / heart / respiratory** – vitals
- **additional_notes** – anything not fitting above
- **owner_instructions** – post-visit instructions
- **initial_diagnosis** – working diagnosis (pre-confirmation)

All fields are optional by design.

---

## API Behavior

### GET
Returns the clinical exam for the appointment.
- `404` if none exists

### POST
Creates a clinical exam.
- Only one exam per appointment
- Fails if exam already exists

### PATCH
Partial update of an existing exam.
- Does not overwrite unspecified fields

### Permissions
- User must belong to the same clinic
- Only vets may create/update
- Read access follows appointment visibility

---

## Serializer Design

- **ClinicalExamWriteSerializer**
  - Allows partial updates
  - Does not accept `clinic`, `appointment`, or `created_by` from client
- **ClinicalExamReadSerializer**
  - Full read-only representation

---

## Migration Strategy

Applied migrations:
- `0003_clinicalexam_alter_medicalrecord_options_and_more`
- `0004_remove_fk_defaults`

Key points:
- Backfilled required FKs once
- Removed defaults afterward to enforce correctness
- Broken migration artifacts were removed before commit

Current migration state is clean:
```bash
python manage.py makemigrations --check --dry-run
```

---

## Developer Tooling

A minimal **Brewfile** is included for local development:

```ruby
brew "ripgrep"
```

Install with:
```bash
brew bundle
```

---

## Test Coverage

New tests:
- `test_exam_create_and_get`
- `test_exam_all_fields_optional`

All tests pass:
```bash
pytest
```

---

## Frontend Notes

Frontend can assume:
- Exam may or may not exist for an appointment
- PATCH is safe for autosave-style UX
- Empty POST payload is valid

---

## Follow-up Ideas (Out of Scope)
- Embed clinical exam summary in Appointment detail response
- Prescription model linked to ClinicalExam
- Final diagnosis vs initial diagnosis
- Visit locking / signing by vet

---

## Status
✔ Tests passing
✔ Migrations clean
✔ Ready for PR
