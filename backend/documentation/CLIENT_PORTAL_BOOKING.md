# Client portal: online booking (backend)

Pet owners can browse **public** clinic info, vets, and free slots, then authenticate with a **one-time code** (OTP) sent to their **registered email**. After confirming the code they receive a **portal JWT** (separate from staff `SimpleJWT`). They can list their pets, book a visit in an available slot, list today’s and future visits, and cancel non-terminal appointments.

## Prerequisites in domain data

1. **`Client`** (owner) with a non-empty **`email`** matching how the user will log in (comparison is case-insensitive).
2. **`ClientClinic`** linking that client to the clinic, with **`is_active=True`**.
3. **`Clinic.online_booking_enabled=True`** (default). If `False`, public routes return **403** and authenticated portal booking routes return **403**.
4. **`Patient`** rows belong to that owner and clinic (portal lists only `patient` where `owner` + `clinic` match the session).
5. Slots follow the same rules as internal scheduling: **`compute_availability`** (vet working hours, holidays, existing appointments). See [AVAILABILITY_API.md](AVAILABILITY_API.md).

## Authentication (portal JWT)

Portal tokens are signed with `SECRET_KEY`, include **`aud: "portal"`**, and are **not** valid on staff endpoints (and vice versa). Send:

```http
Authorization: Bearer <access>
```

where `<access>` is the string returned by `POST /api/portal/auth/confirm-code/`.

### OTP flow

1. **`POST /api/portal/auth/request-code/`**
   Body: `clinic_slug` (string), `email` (string).
   If a membership exists, a **6-digit** code is created. With **`PORTAL_OTP_EMAIL_ENABLED`** and SendGrid configured (**`REMINDER_SENDGRID_API_KEY`**, **`REMINDER_SENDGRID_FROM_EMAIL`**), the code is emailed to the client’s address; otherwise only logs apply (see Configuration).
   Response is always a generic success message to avoid email enumeration when membership is missing.
   **429** if per-IP or per-mailbox rate limits are exceeded (see `PORTAL_OTP_*` limit env vars).
2. **`POST /api/portal/auth/confirm-code/`**
   Body: `clinic_slug`, `email`, `code`.
   Response: `{ "access": "<portal_jwt>" }`.
   **429** if confirm rate limits are exceeded.
3. **Magic link (optional):** each `request-code` also issues a long one-time **token** (digest stored on `PortalLoginChallenge`). **`POST /api/portal/auth/magic-link/`** with body **`{ "token": "<plaintext>" }`** returns the same **`{ "access" }`** as confirm-code. Consuming the token **or** the 6-digit code marks the challenge used; the other method then fails. **429** uses `PORTAL_MAGIC_LINK_*` limits. If **`PORTAL_MAGIC_LINK_URL_TEMPLATE`** is set (must contain `{token}`), the email includes a full sign-in URL; otherwise it includes the raw token for copy-paste.

**Development / tests only:** if `PORTAL_RETURN_OTP_IN_RESPONSE` is enabled (see Configuration), `request-code` may include `_dev_otp` and **`_dev_magic_link_token`**. **Never enable in production.**

## Public endpoints (no JWT)

Base path: **`/api/portal/`**

| Method | Path | Query | Notes |
|--------|------|-------|--------|
| GET | `clinics/<slug>/` | — | `{ slug, name, online_booking_enabled, portal_booking_deposit_pln, portal_booking_deposit_label }` — deposit strings for UI copy (amount may be `"0.00"`) |
| GET | `clinics/<slug>/vets/` | — | List vets (`id`, `first_name`, `last_name`, `username`) |
| GET | `clinics/<slug>/availability/` | `date=YYYY-MM-DD`, optional `vet`, `room` | Same shape as authenticated availability below |

### Availability response shape

- `date`, `timezone`, `clinic_id`, `default_slot_minutes`, `vet_id`, `room_id`
- `closed_reason` (null if open)
- `workday` (`start` / `end` ISO datetimes) or `null`
- `free`: list of `{ "start", "end" }` — **booking must use an exact `start`/`end` pair** from this list for the chosen vet (and room if used).

## Authenticated portal endpoints (portal JWT)

| Method | Path | Purpose |
|--------|------|--------|
| GET | `me/patients/` | Pets linked to this owner in this clinic |
| GET | `me/patients/<id>/` | Pet card: demographics, upcoming visits for this pet, recent vaccinations, last weight from last **completed** visit with `weight_kg` |
| GET | `availability/` | Same query/response as public clinic availability, scoped to token’s clinic |
| GET | `appointments/` | Upcoming sidebar: appointments from **start of local calendar day** onward for this owner’s patients (excludes cancelled); includes **`deposit_invoice_id`**, **`payment_required`** when a portal deposit invoice exists and is not paid |
| POST | `appointments/` | Create visit (see below) |
| POST | `invoices/<invoice_id>/stripe-checkout/` | Start Stripe Checkout (PLN deposit **gross** = invoice `total_gross`); body `success_url`, `cancel_url` |
| POST | `invoices/<invoice_id>/complete-deposit/` | After Checkout: `{ "stripe_session_id" }`, or dev `{ "simulated": true }` |
| POST | `stripe/webhook/` | Stripe `checkout.session.completed` (sign with `STRIPE_WEBHOOK_SECRET`); CSRF-exempt |
| POST | `appointments/<id>/cancel/` | Client cancellation (body optional `cancellation_reason`); cancels linked **draft** deposit invoice in the same transaction |

### `POST /api/portal/appointments/`

JSON body:

- **`patient_id`** (int) — must belong to portal client + clinic
- **`vet_id`** (int) — vet in clinic
- **`starts_at`**, **`ends_at`** — ISO datetimes; must **exactly match** one `free` interval returned for that date/vet (optional `room_id`) or server returns **409**
- **`reason`** (optional string, max 255)
- **`room_id`** (optional int) — must belong to clinic if provided

**Deposit (clinic setting):** `Clinic.portal_booking_deposit_amount` (default `0`). If **> 0**:

- Visit is created with `status=scheduled` (not `confirmed` until deposit is paid).
- A **DRAFT** `Invoice` is created in PLN with one line: label from `portal_booking_deposit_line_label` (default “Online booking deposit”), `unit_price` = deposit amount, **8% VAT** (`InvoiceLine.VatRate.RATE_8`). The appointment stores **`portal_deposit_invoice`**.
- **`POST …/stripe-checkout/`** (requires `STRIPE_SECRET_KEY`) creates a Stripe Checkout Session; charge amount is **gross** PLN (`invoice.total_gross`, one line item). Redirect URLs must be valid `http`/`https`; non-`DEBUG` requires **https**.
- **`POST …/complete-deposit/`** with **`stripe_session_id`**: server retrieves the session from Stripe, verifies **`payment_status=paid`**, metadata matches invoice/appointment/clinic, and **`amount_total`** (within 1 minor unit) matches expected gross; idempotent per session id (`Payment.reference` `stripe:<session_id>`). Confirms visit and audits **`portal_booking_deposit_paid`** when a new payment row is created.
- **Webhook** `POST …/stripe/webhook/` runs the same fulfillment (idempotent). Configure the signing secret in **`STRIPE_WEBHOOK_SECRET`**; returns **503** if unset.
- **Simulated:** `{ "simulated": true }` when `PORTAL_ALLOW_SIMULATED_PAYMENT` **or** `DEBUG`; records net amount `invoice.total` like the original MVP. If **`STRIPE_SECRET_KEY`** is set, an empty **`complete-deposit`** body returns **400** instead of **501**.
- **409** if the appointment was already cancelled (cannot pay).

If deposit amount is zero, behaviour is unchanged: **`status=confirmed`**, no deposit invoice, **`payment_required`** false in API payloads.

Created appointments always use `visit_type=outpatient`.

### `GET /api/portal/me/patients/<id>/`

Returns **404** unless the patient belongs to the portal user for the token’s clinic. Response:

- **`patient`**: `id`, `name`, `species`, `breed`, `sex`, `birth_date`, `microchip_no`, `allergies`, `primary_vet_id`, `primary_vet_name` (clinic internal `notes` and AI fields are omitted).
- **`upcoming_appointments`**: same idea as the global portal appointments list, but only for this pet (from start of local day, not cancelled).
- **`recent_vaccinations`**: last 15 records (`vaccine_name`, `batch_number`, `administered_at`, `next_due_at`, `notes`).
- **`last_weight_kg`**, **`last_weight_recorded_at`**: from the most recent **completed** appointment whose clinical exam has `weight_kg`; both `null` if none.

## Configuration (`config/settings.py` / environment)

| Setting / env | Meaning |
|---------------|--------|
| `PORTAL_OTP_EXPIRE_MINUTES` | OTP validity (default 15). Env: `PORTAL_OTP_EXPIRE_MINUTES` |
| `PORTAL_ACCESS_TOKEN_LIFETIME` | Portal JWT lifetime (default 24h). Env: `PORTAL_ACCESS_TOKEN_HOURS` |
| `PORTAL_RETURN_OTP_IN_RESPONSE` | If true, OTP may appear as `_dev_otp` on request-code. Env: `PORTAL_RETURN_OTP_IN_RESPONSE` (`1`/`true`/`yes`) |
| `PORTAL_OTP_EMAIL_ENABLED` | If true, send login OTP via SendGrid using `REMINDER_SENDGRID_*`. Env: `PORTAL_OTP_EMAIL_ENABLED` |
| `PORTAL_OTP_REQUEST_LIMIT_PER_IP` / `PORTAL_OTP_REQUEST_IP_WINDOW_SEC` | Max `request-code` calls per client IP per window (default 60/hour). |
| `PORTAL_OTP_REQUEST_LIMIT_PER_MAILBOX` / `PORTAL_OTP_REQUEST_MAILBOX_WINDOW_SEC` | Max `request-code` per clinic slug + email (default 10/15 min). |
| `PORTAL_OTP_CONFIRM_LIMIT_PER_IP` / `PORTAL_OTP_CONFIRM_IP_WINDOW_SEC` | Max `confirm-code` attempts per IP (default 80/15 min). |
| `PORTAL_OTP_CONFIRM_LIMIT_PER_MAILBOX` / `PORTAL_OTP_CONFIRM_MAILBOX_WINDOW_SEC` | Max `confirm-code` per slug + email (default 30/15 min). |
| `REMINDER_SENDGRID_API_KEY`, `REMINDER_SENDGRID_FROM_EMAIL`, `REMINDER_SENDGRID_FROM_NAME` | Shared with reminder email delivery; required for portal OTP email. |
| `PORTAL_MAGIC_LINK_URL_TEMPLATE` | Optional email link, e.g. `https://app.example/booking?portal_token={token}` — `{token}` replaced with the secret (must appear once if set). |
| `PORTAL_MAGIC_LINK_LIMIT_PER_IP`, `PORTAL_MAGIC_LINK_IP_WINDOW_SEC` | Throttle `POST …/auth/magic-link/`. |
| `PORTAL_ALLOW_SIMULATED_PAYMENT` | If true (or `DEBUG` true), `POST …/complete-deposit/` may use `{ "simulated": true }`. Env: `PORTAL_ALLOW_SIMULATED_PAYMENT` (`1`/`true`/`yes`) |
| `PORTAL_NOTIFY_STAFF_ON_BOOKING` | If true, staff get in-app notification on portal booking (default on). Env: `PORTAL_NOTIFY_STAFF_ON_BOOKING` |
| `PORTAL_CONFIRM_FAIL_LIMIT_MAILBOX` / `PORTAL_CONFIRM_FAIL_WINDOW_SEC` / `PORTAL_CONFIRM_LOCKOUT_SEC` | Wrong `confirm-code` attempts per slug+email before short lockout (defaults 10 / 900s / 900s). |
| `PORTAL_CONFIRM_FAIL_LIMIT_IP` / `PORTAL_CONFIRM_FAIL_IP_WINDOW_SEC` / `PORTAL_CONFIRM_LOCKOUT_IP_SEC` | Same for per-IP counter (defaults 40 / 900s / 1800s). |
| `STRIPE_SECRET_KEY` | Stripe secret API key; enables Checkout + session retrieve. Env: `STRIPE_SECRET_KEY` |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for `POST …/stripe/webhook/`. Env: `STRIPE_WEBHOOK_SECRET` |
| `DEFAULT_SLOT_MINUTES` | Slot length for availability (default 30) |

## Audit log

Events: **`portal_appointment_booked`** (after payload may include `needs_deposit`, `deposit_invoice_id`), **`portal_appointment_cancelled`**, **`portal_booking_deposit_paid`** (`entity_type=appointment`, `actor` null, `metadata.source=portal`; `simulated=true` for dev flow; Stripe includes `stripe_session_id`, optional `via=stripe_webhook`). See [AUDIT_LOG.md](AUDIT_LOG.md).

## Security notes (MVP gaps)

- **Email delivery** uses SendGrid when `PORTAL_OTP_EMAIL_ENABLED` and `REMINDER_SENDGRID_*` are set; monitor send failures in logs.
- **Rate limiting** on `request-code` / `confirm-code` is enforced via Django cache (use Redis for cache backend in multi-instance deployments).
- **Confirm-code lockout** (separate counters) returns **429** with `Too many invalid code attempts…` after repeated wrong codes for a registered mailbox; successful login or magic-link clears failure counters.
- **Refresh tokens** for portal are not implemented; users repeat OTP when access expires.
- Generic messaging on `request-code` reduces email enumeration but also hides typos until confirm step fails.

## Related code

- App: `apps.portal`
- URLs: `config/urls.py` → `api/portal/`
- Slot validation: `apps.portal.services.booking.portal_slot_matches_availability`
