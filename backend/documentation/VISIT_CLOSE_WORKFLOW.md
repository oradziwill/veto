# Visit Close Workflow

## Purpose

This document describes the **Visit Close** feature added to the scheduling module.
Closing a visit is an explicit action performed by a veterinarian to finalize an appointment.

This workflow is the foundation for:
- Prescriptions
- Invoicing
- Discharge summaries
- Locked medical records

---

## Endpoint

### Close Visit

POST /api/appointments/<appointment_id>/close_visit/

---

## Permissions

- User must be authenticated
- User must belong to the same clinic as the appointment
- User must have `is_vet = True`

---

## Behavior

### Success
- HTTP 200 or 204
- Appointment status is transitioned to a final state (e.g. `completed`)
- Visit is considered closed and immutable for downstream logic

---

### Error Handling

| Condition | Status |
|---------|--------|
| User is not a vet | 403 |
| Appointment not found in clinic | 404 |
| Appointment does not exist | 404 |
| No clinical exam exists | 400 |

---

## Validation Rules

- Appointment **must reference a valid vet user**
- Appointment **must belong to user’s clinic**
- Appointment **must have a ClinicalExam**

---

## Tests

Covered scenarios:
- Vet can close visit (happy path)
- Non-vet is forbidden
- Cross-clinic access returns 404
- Exam requirement enforced

Test file:


---

## Design Notes

- Closing a visit is **explicit**, not automatic
- Visit lifecycle is enforced at the API level
- Enables safe downstream features

---

## Next Planned Features

- Prescriptions linked to closed visits
- Exam locking after closure
- Billing / invoices
- Visit audit log
