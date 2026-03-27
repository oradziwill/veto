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
  - If `settings.REQUIRE_DISCHARGE_SAFETY_FOR_DISCHARGE=True`, discharge is blocked when safety checks have blocking reasons.
  - Error payload includes `blocking_reasons` and `warnings`.
- **Discharge safety checks**: `GET /api/hospital-stays/<id>/discharge-safety-checks/`
  - Returns:
    - `ready_to_discharge` (bool)
    - `blocking_reasons[]`
    - `warnings[]`

### Hospital Rounds Notes (new)

To avoid creating extra appointments during hospitalization:

- **List notes**: `GET /api/hospital-stays/<id>/notes/`
- **Create note**: `POST /api/hospital-stays/<id>/notes/`
  - Body:
    - `note_type` (optional, default `"round"`)
    - `note` (required)
    - `vitals` (optional JSON object, e.g. `{ "temp_c": 38.7, "hr_bpm": 110 }`)
- **Update note**: `PATCH /api/hospital-stays/<id>/notes/<note_id>/`
- **Delete note**: `DELETE /api/hospital-stays/<id>/notes/<note_id>/`

### Hospital Tasks (new)

Track treatment tasks within one hospitalization stay:

- **List tasks**: `GET /api/hospital-stays/<id>/tasks/`
- **Create task**: `POST /api/hospital-stays/<id>/tasks/`
  - Body:
    - `title` (required)
    - `description` (optional)
    - `priority` (`low|normal|high`, default `normal`)
    - `status` (`pending|in_progress|completed|cancelled`, default `pending`)
    - `due_at` (optional datetime)
- **Update task**: `PATCH /api/hospital-stays/<id>/tasks/<task_id>/`
- **Delete task**: `DELETE /api/hospital-stays/<id>/tasks/<task_id>/`

When task status is changed to `completed`, backend auto-fills:
- `completed_at`
- `completed_by`

### Medication MAR (new)

Medication orders and administration events inside one hospitalization stay:

- **List medication orders**: `GET /api/hospital-stays/<id>/medications/`
- **Create medication order**: `POST /api/hospital-stays/<id>/medications/`
  - Body:
    - `medication_name` (required)
    - `dose` (required, decimal)
    - `dose_unit` (optional, default `mg`)
    - `route` (optional, e.g. `iv`, `oral`)
    - `frequency_hours` (optional, default `8`)
    - `starts_at` (required datetime)
    - `ends_at` (optional datetime)
    - `instructions` (optional)
    - `is_active` (optional, default `true`)
- **Update medication order**: `PATCH /api/hospital-stays/<id>/medications/<medication_id>/`
- **Delete medication order**: `DELETE /api/hospital-stays/<id>/medications/<medication_id>/`

Administration events:

- **List administrations**: `GET /api/hospital-stays/<id>/medications/<medication_id>/administrations/`
- **Create administration event**: `POST /api/hospital-stays/<id>/medications/<medication_id>/administrations/`
  - Body:
    - `scheduled_for` (optional datetime)
    - `administered_at` (optional datetime)
    - `status` (`pending|given|skipped`, default `pending`)
    - `note` (optional)
- **Update administration event**: `PATCH /api/hospital-stays/<id>/medications/<medication_id>/administrations/<administration_id>/`

Auto-behavior:
- if status is set to `given` and `administered_at` is empty:
  - backend sets `administered_at=now`
  - backend sets `administered_by=request.user`
- if status changes from `given` to another status:
  - backend clears `administered_at` and `administered_by`

### Medication Schedule Generator (new)

Generate pending administration schedule entries for active medication orders (idempotent).

- **Generate schedule**: `POST /api/hospital-stays/<id>/medications/generate-schedule/?horizon_hours=24&past_hours=12`
  - `horizon_hours`: integer \(1..336\), default `24`
  - `past_hours`: integer \(0..336\), default `12`

Response:
- `created` number of administrations created
- `skipped_existing` number of already-existing scheduled entries in the window

### Medication Due Alerts (new)

Returns active medication orders that are due now/soon for a hospitalization stay:

- **Due medications**: `GET /api/hospital-stays/<id>/medications-due/?window_minutes=30&include_overdue=1`
  - `window_minutes`: integer \(0..1440\), default `30`
  - `include_overdue`: `1|0`, default `1`

Response:
- `items[]` with:
  - `medication_order` (full order payload)
  - `last_given_at` (nullable datetime)
  - `next_due_at` (datetime)
  - `is_overdue` (bool)
  - `overdue_minutes` (int)

### Discharge Summary API (new)

Structured discharge summary per hospitalization stay (one summary per stay):

- **Get summary**: `GET /api/hospital-stays/<id>/discharge-summary/`
  - Returns saved summary (`source=saved`) or backend-generated draft (`source=draft`).
- **Save summary**: `PUT /api/hospital-stays/<id>/discharge-summary/`
  - Body:
    - `diagnosis` (text)
    - `hospitalization_course` (text)
    - `procedures` (text)
    - `medications_on_discharge` (JSON array)
    - `home_care_instructions` (text)
    - `warning_signs` (text)
    - `follow_up_date` (date, optional)
- **Finalize summary**: `POST /api/hospital-stays/<id>/discharge-summary/finalize/`
  - Allowed only after hospital stay status is `discharged`.
  - Sets `finalized_at` and `generated_by`.
- **Download summary PDF**: `GET /api/hospital-stays/<id>/discharge-summary/pdf/`
  - Returns `application/pdf` attachment.
  - Requires saved summary (returns 404 if summary does not exist yet).

Current blocking checks before discharge:
- missing saved discharge summary
- missing `home_care_instructions` in summary
- missing `warning_signs` in summary
- open high-priority hospital tasks

### Workflow

1. Create hospitalization appointment (or use existing)
2. Create HospitalStay linked to admission appointment
3. During stay, staff records rounds in `notes` and treatment plan in `tasks`
4. Discharge when ready

### Nursing Dashboard (new)

Clinic-wide triage view for active hospital stays:

- **Dashboard**: `GET /api/hospital-stays/nursing-dashboard/?window_minutes=30&limit=50`
  - Accessible to clinic `staff` and `vet` roles.
  - Returns admitted stays enriched with:
    - `last_round_note`, `last_round_at`
    - `open_high_priority_tasks`
    - `meds_overdue`, `meds_due_soon` (computed within the requested window)

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
