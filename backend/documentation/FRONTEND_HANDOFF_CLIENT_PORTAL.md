# Frontend handoff: client portal (online booking)

Backend reference: [CLIENT_PORTAL_BOOKING.md](CLIENT_PORTAL_BOOKING.md).

## Assumptions for routing

- Each clinic has a unique **`slug`** (e.g. `test-clinic`). Expose booking at something like `/book/:clinicSlug` or `booking.{clinicSlug}.yourdomain`.
- All portal API calls use the same API host as the rest of the app (e.g. `http://localhost:8000`), path prefix **`/api/portal/`** (see [config/urls.py](../config/urls.py)).

## Auth: keep portal JWT separate from staff JWT

Portal access is **`{ "access": "<token>" }`** from `confirm-code`. It is **not** a SimpleJWT staff token (`/api/auth/token/`). Use a dedicated storage key (e.g. `portal_access`) and **do not** send it to `/api/appointments/`, `/api/auth/*`, etc.

```http
Authorization: Bearer <portal_access>
```

Only these paths below need the portal Bearer header.

## Suggested UX flow

1. **Landing (no login)**
   - `GET /api/portal/clinics/<slug>/` — show name plus **`portal_booking_deposit_pln`** / **`portal_booking_deposit_label`** when you want to disclose prepayment; handle 404 (bad slug) and 403 (`online_booking_enabled=false`).
2. **Choose vet + date**
   - `GET /api/portal/clinics/<slug>/vets/`
   - `GET /api/portal/clinics/<slug>/availability/?date=YYYY-MM-DD&vet=<id>`
   - Render `free[]` as selectable slots (each item has `start` and `end` ISO strings).
3. **Login**
   - Email step: `POST /api/portal/auth/request-code/` with `{ "clinic_slug", "email" }`.
   - Show one generic success message (backend intentionally does not reveal whether the email exists).
   - **Code step:** `POST /api/portal/auth/confirm-code/` with `{ "clinic_slug", "email", "code" }` → store `access`.
   - **Magic link (alternative):** read `token` from the email link query/hash (see **`PORTAL_MAGIC_LINK_URL_TEMPLATE`**) or paste the token; `POST /api/portal/auth/magic-link/` with `{ "token" }` → store `access`. Same challenge as the code — using one invalidates the other.
   - **Local/dev only:** response may contain `_dev_otp` and `_dev_magic_link_token` when `PORTAL_RETURN_OTP_IN_RESPONSE` is enabled — never rely on this in production UI.
4. **After login**
   - `GET /api/portal/me/patients/` — pet picker.
   - `GET /api/portal/me/patients/<id>/` — **pet card** (demographics, upcoming visits for that pet, vaccinations, last weight). **404** if the pet is not yours in this clinic.
   - Optionally re-fetch `GET /api/portal/availability/?date=&vet=` (same shape as public) to refresh slots before submit.
5. **Book**
   - `POST /api/portal/appointments/` with exact `starts_at` / `ends_at` from a **fresh** `free` slot (see contract below).
   - If the clinic’s configured deposit is non-zero (see **`portal_booking_deposit_pln`** on the public clinic payload), response **`status`** is **`scheduled`** and **`payment_required`** is true until deposit is paid; use **`deposit_invoice_id`** with **`POST …/invoices/<id>/complete-deposit/`** (see below).
6. **Deposit**
   - **Stripe (production):** `POST /api/portal/invoices/<deposit_invoice_id>/stripe-checkout/` with **`success_url`** and **`cancel_url`** (HTTPS in production; both required). Response **`checkout_url`**, **`session_id`**. Open **`checkout_url`** in the browser; on success Stripe redirects to **`success_url`** — include **`{CHECKOUT_SESSION_ID}`** in the query string (see Stripe docs) so the SPA can read the session id and call **`POST …/complete-deposit/`** with **`{ "stripe_session_id": "<id>" }`**. The backend also accepts Stripe **`checkout.session.completed`** webhooks at **`POST /api/portal/stripe/webhook/`** (server-side secret: **`STRIPE_WEBHOOK_SECRET`**).
   - **Simulated (dev):** **`POST …/complete-deposit/`** with **`{ "simulated": true }`** when `PORTAL_ALLOW_SIMULATED_PAYMENT` or **`DEBUG`** allows it.
7. **My visits**
   - `GET /api/portal/appointments/` — list from start of **today (server local calendar day)** onward, excludes cancelled; each row may include **`deposit_invoice_id`** and **`payment_required`**.
8. **Cancel**
   - `POST /api/portal/appointments/<id>/cancel/` with optional `{ "cancellation_reason": "..." }` — **204** on success; a linked **draft** deposit invoice is cancelled in the same transaction.

## Endpoints (concise)

| Step | Method | Path |
|------|--------|------|
| Clinic | GET | `/api/portal/clinics/<slug>/` |
| Vets | GET | `/api/portal/clinics/<slug>/vets/` |
| Slots (public) | GET | `/api/portal/clinics/<slug>/availability/?date=...&vet=...&room=...` |
| Request OTP | POST | `/api/portal/auth/request-code/` |
| Magic link login | POST | `/api/portal/auth/magic-link/` |
| Confirm OTP | POST | `/api/portal/auth/confirm-code/` |
| Pets | GET | `/api/portal/me/patients/` |
| Pet card | GET | `/api/portal/me/patients/<id>/` |
| Slots (auth, optional) | GET | `/api/portal/availability/?date=...&vet=...` |
| List visits | GET | `/api/portal/appointments/` |
| Book | POST | `/api/portal/appointments/` |
| Start Stripe Checkout | POST | `/api/portal/invoices/<invoice_id>/stripe-checkout/` |
| Complete deposit | POST | `/api/portal/invoices/<invoice_id>/complete-deposit/` |
| Stripe webhook | POST | `/api/portal/stripe/webhook/` |
| Cancel | POST | `/api/portal/appointments/<id>/cancel/` |

## Request / response contracts

### `POST .../auth/request-code/`

```json
{ "clinic_slug": "test-clinic", "email": "owner@example.com" }
```

Response (always **200** if slug valid and booking enabled):

```json
{ "detail": "If this email is registered at the clinic, a login code was sent." }
```

Do not branch UI on “email exists unknown” — same copy for all successful responses.

### `POST .../auth/magic-link/`

After `request-code`, the email (or dev **`_dev_magic_link_token`**) contains a long **token** — no `clinic_slug` / `email` in the request (token identifies the challenge).

```json
{ "token": "<one-time token>" }
```

Success **200**: `{ "access": "<portal_jwt>" }` — same shape as confirm-code. **400** if invalid/expired/already used. **403** if `online_booking_enabled` is false for that clinic. **429** on too many attempts.

### `POST .../auth/confirm-code/`

```json
{
  "clinic_slug": "test-clinic",
  "email": "owner@example.com",
  "code": "123456"
}
```

Success **200**:

```json
{ "access": "<portal_jwt>" }
```

Invalid / expired **400**: `{ "detail": "Invalid or expired code." }`

Use **either** magic-link **or** 6-digit code for a given challenge — not both.

### `POST .../appointments/`

Use **`starts_at` and `ends_at` exactly** as returned in `free[].start` / `free[].end` for the same `date`, `vet` (and `room` if you use room-scoped availability).

```json
{
  "patient_id": 1,
  "vet_id": 2,
  "starts_at": "2026-03-30T09:00:00+02:00",
  "ends_at": "2026-03-30T09:30:00+02:00",
  "reason": "Annual checkup"
}
```

Success **201**: appointment summary: `id`, `starts_at`, `ends_at`, `status`, `reason`, `vet_id`, `patient_id`, plus **`payment_required`**, **`deposit_invoice_id`**, **`deposit_net_pln`**, **`deposit_gross_pln`** (latter two are string decimals; net is invoice total, gross uses line `line_gross` with 8% VAT on the deposit line). If clinic deposit is zero, **`status`** is **`confirmed`** and payment fields reflect no deposit.

**409** — `"Selected time is no longer available."` — refresh availability and ask user to pick another slot.

### `POST .../invoices/<invoice_id>/stripe-checkout/`

```json
{
  "success_url": "https://app.example/booking/success?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://app.example/booking/cancel"
}
```

- **200** — `{ "checkout_url", "session_id" }`
- **400** — missing/invalid URLs, non-PLN invoice, not draft.
- **501** — `STRIPE_SECRET_KEY` not configured.

### `POST .../invoices/<invoice_id>/complete-deposit/`

Either after Checkout:

```json
{ "stripe_session_id": "cs_..." }
```

or Dev simulation:

```json
{ "simulated": true }
```

- **200** — deposit recorded; visit **`confirmed`** when invoice fully paid; response body matches the booking summary shape from create.
- **400** — wrong body (e.g. empty when Stripe is configured), invoice/session mismatch, session not paid, etc.
- **403** — simulated payments disabled (`PORTAL_ALLOW_SIMULATED_PAYMENT` false and `DEBUG` false).
- **404** — invoice not found or not this client’s portal deposit invoice.
- **409** — appointment already cancelled.
- **501** — Stripe not configured and no usable `simulated`; or cannot verify session with Stripe.
- **502** — Stripe API error when retrieving the session.

## Availability payload (for UI)

Typical fields:

- `closed_reason` — if set, show as “closed” (holiday, vet off, etc.) and hide slot grid.
- `free` — array of `{ start, end }` ISO datetimes (timezone-aware).
- `default_slot_minutes` — slot length for labels (“30 min”).

## HTTP errors to handle

| Status | Typical cause |
|--------|----------------|
| 400 | Missing/invalid query or JSON fields |
| 403 | `online_booking_disabled` for clinic |
| 404 | Unknown `slug`, vet id, patient, or appointment |
| 409 | Slot taken / no longer matches `free` (booking) |
| 429 | Too many OTP `request-code` or `confirm-code` attempts (rate limits); ask user to wait |

Portal JWT **expired or invalid** behaves like other JWT endpoints (**401**) once you wire global API error handling for `Authorization`.

## CORS

Backend allows configured dev origins (see `CORS_ALLOWED_ORIGINS` in [settings](../config/settings.py)). Add your frontend origin if needed.

## Implementation tips

1. **Race on book:** between selecting a slot and submitting, another user (or staff) may take it — handle **409** with a friendly retry + refresh slots.
2. **Timezone:** display `start`/`end` in the user’s or clinic timezone; send back the same ISO strings the API returned to avoid mismatch.
3. **No refresh token:** after `PORTAL_ACCESS_TOKEN_LIFETIME` the user repeats OTP — show a calm “session expired, log in again” state.
4. **Production:** enable **`PORTAL_OTP_EMAIL_ENABLED`** and SendGrid (`REMINDER_SENDGRID_*`) so codes are emailed; handle **429** on auth with a calm “try again later” message. Dev may use `_dev_otp` when enabled server-side.

## Related docs

- [CLIENT_PORTAL_BOOKING.md](CLIENT_PORTAL_BOOKING.md) — backend behaviour, env vars, audit.
- [AVAILABILITY_API.md](AVAILABILITY_API.md) — same availability engine as internal staff calendar (conceptual overlap).
