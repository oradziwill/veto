# Frontend handoff: recent backend work (bundle)

Single entry point for frontend integration of features shipped together on the backend: **clinical exam templates**, **client portal (online booking)**, and **audit log extensions** (admin UI). Deeper detail lives in the linked focused handoffs.

**Staff app — tylko portal add‑ony (KPI, RODO, powiadomienia):** [FRONTEND_HANDOFF_STAFF_PORTAL_ADDONS.md](FRONTEND_HANDOFF_STAFF_PORTAL_ADDONS.md)

---

## 1. Clinical exam templates (staff app)

**Auth:** normal staff JWT (`/api/auth/token/`), same as other medical endpoints. Doctor or clinic admin.

### Endpoints

| Method | Path |
|--------|------|
| GET | `/api/medical/clinical-exam-templates/` |
| POST | `/api/medical/clinical-exam-templates/` |
| PATCH | `/api/medical/clinical-exam-templates/<id>/` |
| DELETE | `/api/medical/clinical-exam-templates/<id>/` |
| POST | `/api/appointments/<id>/exam/apply-template/` |

### Apply template (visit screen)

Request:

```json
{
  "template_id": 12,
  "force": false
}
```

- `force=false` (default): only fills **empty** template-backed fields on the exam.
- `force=true`: overwrites those fields from the template.

Response: full **ClinicalExam** payload plus **`template_meta`**: `template_id`, `template_name`, `applied_fields`, `force`.

**UI ideas:** template dropdown on the exam panel; highlight fields listed in `applied_fields`; toggle “Overwrite existing values” → `force: true`.

**Full detail:** [FRONTEND_HANDOFF_CLINICAL_EXAM_TEMPLATES.md](FRONTEND_HANDOFF_CLINICAL_EXAM_TEMPLATES.md) · [CLINICAL_EXAM_DOCUMENTATION.md](CLINICAL_EXAM_DOCUMENTATION.md)

### 1b. Procedure supply templates (suggested consumables per procedure)

**Auth:** staff JWT. **CRUD** (create list of inventory lines with suggested quantities): **doctor or clinic admin** only — same as clinical exam templates.

| Method | Path |
|--------|------|
| GET | `/api/medical/procedure-supply-templates/` |
| POST | `/api/medical/procedure-supply-templates/` |
| GET / PATCH / DELETE | `/api/medical/procedure-supply-templates/<id>/` |
| POST | `/api/appointments/<id>/procedure-supply-template-preview/` |
| GET | `/api/patients/<id>/recent-supply-lines/` |

**List query (`GET …/procedure-supply-templates/`):**

- `visit_type` — exact match on template tag (free text, e.g. `usg` / `imaging`; **not** the appointment enum `outpatient` / `hospitalization`).
- `visit_type_icontains` — optional partial match on the same field (can be combined with `visit_type`).
- `for_appointment=<appointment_id>` — optional. Verifies the appointment belongs to the user’s clinic; otherwise **404**. When present, the response is an object: **`appointment_context`** (`appointment_id`, `patient_id`, `appointment_visit_type`, `reason`) and **`templates`** (array). When omitted, the response stays a **plain JSON array** (backward compatible).

**Recent consumables (`GET …/patients/<id>/recent-supply-lines/`):** staff / vet (same idea as `last-vitals`). Suggestions from past **invoice lines** linked to **inventory** for this patient in this clinic (deduped by item, newest invoice first). **Draft** and **cancelled** invoices are excluded (only sent / paid / overdue count). Query: `limit` (default 20, max 50). Each element: `inventory_item_id`, `name`, `sku`, `unit`, `last_quantity`, `last_used_at`, `invoice_id`. Read-only — does not create invoices or move stock.

**Body (create / full update):** `name`, optional `visit_type`, `is_active`, **`lines`**: array of `{ inventory_item, suggested_quantity, sort_order?, is_optional?, default_unit_price?, vat_rate?, notes? }`. At least one line on create. `suggested_quantity` must be a **positive whole number** (inventory dispense rules). Items must belong to the same clinic.

**PATCH** without `lines` updates only header fields; with `lines` **replaces** all lines.

**Preview (any staff / vet):** `POST …/procedure-supply-template-preview/` with `{ "template_id": <id> }`. Returns `template_id`, `template_name`, `suggested_lines[]` (fields aligned with pre-filling invoice lines: `inventory_item_id`, `description`, quantities, `vat_rate`, `stock_on_hand`, `inventory_item_is_active`, etc.). **Does not** create an invoice or move stock — FE merges into the draft invoice UI; user edits before save.

Inactive templates or wrong-clinic `template_id` → **404**. Inactive inventory items may still appear in `suggested_lines` with `inventory_item_is_active: false`.

---

## 2. Client portal — online booking (owner-facing)

**Auth:** **separate** portal JWT — **not** staff SimpleJWT. Obtain via OTP flow; store under e.g. `portal_access` and send **only** to `/api/portal/*`.

```http
Authorization: Bearer <portal_access>
```

### Public (no token)

| Method | Path |
|--------|------|
| GET | `/api/portal/clinics/<slug>/` |
| GET | `/api/portal/clinics/<slug>/vets/` |
| GET | `/api/portal/clinics/<slug>/availability/?date=YYYY-MM-DD&vet=<id>&room=<id optional>` |

### OTP

1. `POST /api/portal/auth/request-code/` — `{ "clinic_slug", "email" }` — generic **200** message (no email enumeration).
2. `POST /api/portal/auth/magic-link/` — `{ "token" }` — one-time token from email (or dev `_dev_magic_link_token`) → same **`access`** JWT as confirm-code; mutually exclusive with the 6-digit code for the same challenge.
3. `POST /api/portal/auth/confirm-code/` — `{ "clinic_slug", "email", "code" }` → `{ "access": "<jwt>" }`.

Dev/staging only: `_dev_otp` and `_dev_magic_link_token` on request-code when backend flag is enabled — do not use in production.

### Authenticated portal

| Method | Path |
|--------|------|
| GET | `/api/portal/me/patients/` |
| GET | `/api/portal/me/patients/<id>/` | **Pet card** (demographics, upcoming visits for this pet, recent vaccinations, last weight from completed visit) |
| GET | `/api/portal/availability/?date=&vet=` |
| GET | `/api/portal/appointments/` |
| POST | `/api/portal/appointments/` |
| POST | `/api/portal/invoices/<invoice_id>/complete-deposit/` |
| POST | `/api/portal/invoices/<invoice_id>/stripe-checkout/` |
| POST | `/api/portal/stripe/webhook/` | Stripe Dashboard → backend (not called by SPA) |
| POST | `/api/portal/appointments/<id>/cancel/` |

**Clinic public payload** (`GET …/clinics/<slug>/`) also includes **`portal_booking_deposit_pln`** (string, may be `"0.00"`) and **`portal_booking_deposit_label`** so the UI can show prepayment before login.

**Book:** `patient_id`, `vet_id`, `starts_at`, `ends_at` must **exactly** match a `free[]` slot from availability for that date/vet; optional `reason`, `room_id`. **409** if slot gone — refresh grid.

When the clinic’s configured deposit is **> 0**, the new visit is **`scheduled`** (not `confirmed`) until deposit is settled. Production path: **`POST …/stripe-checkout/`** with **`success_url`** / **`cancel_url`** → open **`checkout_url`**; after payment, Stripe redirects to **`success_url`** (use Stripe’s `{CHECKOUT_SESSION_ID}` placeholder) and the app calls **`POST …/complete-deposit/`** with **`stripe_session_id`**, or relies on **`POST …/stripe/webhook/`** (configure `STRIPE_WEBHOOK_SECRET` in Stripe). Dev: **`complete-deposit`** with **`simulated: true`** when allowed. With **`STRIPE_SECRET_KEY`** set, calling **`complete-deposit`** with an empty body returns **400** (expects `stripe_session_id` or `simulated`). With no Stripe key and no `simulated`, **501**. List/detail rows expose **`deposit_invoice_id`** and **`payment_required`**. Cancelling cancels a linked **draft** deposit invoice.

**403** on clinic when `online_booking_enabled` is false.

**Pet card (`GET …/me/patients/<id>/`):** JSON with `patient` (no internal `notes` / AI fields), `upcoming_appointments`, `recent_vaccinations`, `last_weight_kg` (number or null), `last_weight_recorded_at`. **404** if the pet is not owned by this client in this clinic.

**Staff calendar (staff JWT, `/api/appointments/`):** query **`booked_via_portal=true`** (or **`false`**, **`1`**, **`0`**) to show only visits booked via the owner portal vs only those created in the clinic app. List/retrieve payloads include read-only **`booked_via_portal`**.

**Staff — portal booking KPI (staff JWT):** `GET /api/reports/portal-booking-metrics/?from=YYYY-MM-DD&to=YYYY-MM-DD` (optional `date_from` / `date_to`). Defaults to last 30 days if dates omitted. Response: `appointments_total`, `appointments_booked_via_portal`, `share_portal`. Any clinic staff role (`IsStaffOrVet`).

**Staff — in-app notifications:** when an owner books online, doctors/receptionists/admins in that clinic receive a notification with kind **`portal_appointment_booked`** (toggle server-side: `PORTAL_NOTIFY_STAFF_ON_BOOKING`).

**Clinic admin — owner data export (RODO bundle):** `GET /api/clients/<id>/gdpr-export/` — JSON for that client scoped to the admin’s clinic; **403** for non-admins. Emits audit `client_gdpr_export_downloaded`.

**Full detail:** [FRONTEND_HANDOFF_CLIENT_PORTAL.md](FRONTEND_HANDOFF_CLIENT_PORTAL.md) · [CLIENT_PORTAL_BOOKING.md](CLIENT_PORTAL_BOOKING.md)

---

## 3. Audit log (clinic admin UI)

If you build or extend an **admin audit** screen:

- `GET /api/audit-logs/` — clinic admin only; filters: `action`, `entity_type`, `entity_id`, `from`, `to`.

**New / relevant `action` values for the above features:**

| `action` | Notes |
|----------|--------|
| `clinical_exam_template_created` | `entity_type=clinical_exam_template` |
| `clinical_exam_template_updated` | before / after payload |
| `clinical_exam_template_deleted` | |
| `clinical_exam_template_applied` | `entity_type=appointment`; metadata has template + applied_fields |
| `procedure_supply_template_created` / `updated` / `deleted` | `entity_type=procedure_supply_template` |
| `portal_appointment_booked` | `entity_type=appointment`; `actor` may be null; `metadata.source=portal` |
| `portal_appointment_cancelled` | |
| `portal_booking_deposit_paid` | `entity_type=appointment`; simulated checkout; `metadata.simulated=true` |
| `client_gdpr_export_downloaded` | `entity_type=client`; clinic admin downloaded GDPR JSON |

**Full detail:** [AUDIT_LOG.md](AUDIT_LOG.md)

---

## 4. Global API behaviour (FYI)

- Unauthenticated calls to protected staff endpoints should receive **401** (not 403) when using current backend auth stack.
- Portal and staff tokens both use `Bearer`; keep **two clients or two header modes** so portal token is never sent to `/api/appointments/` staff routes.

---

## 5. Other handoffs (unchanged scope)

Not part of the same delivery but available:

- [FRONTEND_HANDOFF_backend-core-v1.md](FRONTEND_HANDOFF_backend-core-v1.md)
- [FRONTEND_HANDOFF_HOSPITALIZATION.md](FRONTEND_HANDOFF_HOSPITALIZATION.md)
- [FRONTEND_HANDOFF_inventory.md](FRONTEND_HANDOFF_inventory.md)
- [SCHEDULING_ASSISTANT.md](SCHEDULING_ASSISTANT.md) — scheduling assistant / capacity (staff)
- [CONSENT_DOCUMENTS.md](CONSENT_DOCUMENTS.md) — zgody na zabieg (PDF, podpis, S3, API)
