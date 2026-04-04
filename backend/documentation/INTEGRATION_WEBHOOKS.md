# Outbound integration webhooks

Clinic admins can register HTTPS endpoints that receive JSON **POST** payloads when selected audit-aligned events occur.

## API (staff JWT, clinic admin only)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/webhooks/subscriptions/` | List subscriptions for accessible clinics |
| POST | `/api/webhooks/subscriptions/` | Create |
| GET | `/api/webhooks/subscriptions/<id>/` | Retrieve |
| PATCH | `/api/webhooks/subscriptions/<id>/` | Partial update |
| PUT | `/api/webhooks/subscriptions/<id>/` | Full update |
| DELETE | `/api/webhooks/subscriptions/<id>/` | Delete |

### Create body

- `target_url` — `http://` or `https://`
- `event_types` — non-empty list of event keys (see below)
- `description` — optional
- `secret` — optional; if set, sends `X-Veto-Webhook-Signature: sha256=<hex>` (HMAC-SHA256 over the raw JSON body, UTF-8)
- `is_active` — default `true`

`secret` is **write-only** (never returned on GET).

### Event types (initial)

| Value | When |
| ----- | ---- |
| `portal_appointment_booked` | Portal books an appointment |
| `portal_appointment_cancelled` | Portal cancels an appointment |
| `portal_booking_deposit_paid` | Deposit invoice marked paid (portal or Stripe) |
| `invoice_payment_recorded` | Staff records a payment on an invoice |

More types can be added in `apps.webhooks.models.WebhookEventType` and `apps.webhooks.dispatch`.

## Payload shape

```json
{
  "event": "portal_appointment_booked",
  "clinic_id": 1,
  "occurred_at": "2026-01-15T12:34:56.789123+00:00",
  "entity_type": "appointment",
  "entity_id": "42",
  "data": {
    "after": { },
    "metadata": { },
    "actor_id": null
  }
}
```

`after` / `metadata` mirror the audit log fields. `actor_id` is set for staff JWT actions when present.

## Delivery behavior

- Each matching subscription creates a `WebhookDelivery` row and POSTs in a **background thread** (non-blocking for the API), **after** the surrounding DB transaction commits (`transaction.on_commit`).
- Set **`WEBHOOK_DELIVERY_USE_THREAD=0`** to deliver synchronously in-process (local tests / debugging only; blocks the request).
- Timeouts: **15s**. Responses are truncated for storage on the delivery record.
- Failures (network, HTTP error) mark the delivery `failed` with `error` / `http_status` when applicable.

## Django admin

`WebhookSubscription` and `WebhookDelivery` are registered for support / debugging.
