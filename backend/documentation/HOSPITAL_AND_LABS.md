# Hospital Visits & Lab Integration

## 1. Visit Types & Hospitalization

### Appointment.visit_type

Appointments now have a `visit_type` field:

- **outpatient** (default) – Regular clinic visit
- **hospitalization** – Admission to clinic hospital

Filter: `GET /api/appointments/?visit_type=hospitalization`

### Hospital Stay

For in-patient hospitalization, use **HospitalStay**:

- **Create**: `POST /api/hospital-stays/` (Doctor/Admin only)
  - `patient`, `attending_vet`, `admitted_at` required
  - Optional: `admission_appointment`, `reason`, `cage_or_room`
- **Discharge**: `POST /api/hospital-stays/<id>/discharge/`
  - Body: `{ "discharge_notes": "..." }`

### Workflow

1. Create hospitalization appointment (or use existing)
2. Create HospitalStay linked to admission appointment
3. Patient is admitted; daily care as needed
4. Discharge when ready

---

## 2. Labs

### Lab Types

- **in_clinic** – Lab within the clinic (clinic FK required)
- **external** – External lab (clinic null, shared across clinics)

### Lab Order Flow

1. **Create order** – `POST /api/lab-orders/`
   - `patient`, `lab`, `lines: [{ test, notes }]` required
   - Optional: `appointment`, `hospital_stay`, `clinical_notes`
2. **Send** – `POST /api/lab-orders/<id>/send/` (draft → sent)
3. **Enter results** – `POST /api/lab-orders/<id>/enter-result/` (Doctor/Admin)
   - Body: `{ "order_line_id": 1, "value": "5.2", "status": "completed" }`

### Seed Data

- In-clinic lab: "Veto Clinic Lab"
- Tests: CBC, Biochemistry Panel, Urinalysis
