# Reminder Engine MVP

This document describes the first backend reminder pipeline for appointments, vaccinations, and invoices.

## Scope

- Reminder queue model (`apps.reminders.models.Reminder`)
- Read/resend API (`/api/reminders/`)
- Consent/preferences API (`/api/reminder-preferences/`)
- Queue hydration command (`enqueue_reminders`)
- Delivery processing command (`process_reminders`)
- Delivery channel abstraction with provider-agnostic placeholders (`email`, `sms`)
- Provider webhook endpoint for delivery status updates

## Data Model

Each reminder is clinic-scoped and linked to exactly one source object:

- appointment reminder (`appointment_id`)
- vaccination reminder (`vaccination_id`)
- invoice reminder (`invoice_id`)

Key fields:

- `reminder_type`: `appointment|vaccination|invoice`
- `channel`: `email|sms`
- `status`: `queued|sent|failed|cancelled`
- `scheduled_for`, `sent_at`
- `attempts`, `max_attempts`, `last_error`
- `provider`, `provider_message_id`, `provider_status`, `delivered_at`

`ReminderPreference` stores per-client, per-clinic compliance settings:

- `allow_email`, `allow_sms`
- `preferred_channel` (`auto|email|sms`)
- `timezone`
- `quiet_hours_start`, `quiet_hours_end`

## API

### List reminders

`GET /api/reminders/`

Optional filters:

- `status`
- `type`
- `channel`

### Retrieve reminder

`GET /api/reminders/<id>/`

### Resend reminder (admin only)

`POST /api/reminders/<id>/resend/`

Resend resets attempts/errors and sets status to `queued` with immediate scheduling.

### Reminder preferences

`GET/POST/PATCH /api/reminder-preferences/`

Preferences are clinic-scoped. Client must be an active member of the clinic.

### Provider webhook callback

`POST /api/reminders/webhooks/<provider>/`

Expected payload:

```json
{
  "message_id": "email-123",
  "status": "delivered",
  "error": ""
}
```

If `REMINDER_WEBHOOK_TOKEN` is set, include `X-Reminder-Webhook-Token` header.

## Commands

### Enqueue reminders

```bash
python manage.py enqueue_reminders
python manage.py enqueue_reminders --appointment-hours 24 --vaccination-days 30 --invoice-days 7
```

Behavior:

- appointments: upcoming scheduled/confirmed visits
- vaccinations: next due date within configured window
- invoices: sent/overdue invoices due within configured window
- duplicate enqueue is prevented for existing non-cancelled reminders of the same source/channel/type
- channel and recipient are chosen from preference + consent + available owner contact

### Process queue

```bash
python manage.py process_reminders
python manage.py process_reminders --limit 200 --retry-minutes 10
```

Behavior:

- sends queued reminders with `scheduled_for <= now`
- applies consent checks before sending; non-consented reminders become `cancelled`
- defers reminders that fall in quiet-hours window (`deferred` status + rescheduled time)
- on success: marks `sent`
- on failure: increments attempts and either re-queues (`queued`) or terminally fails (`failed`) when attempts reach `max_attempts`

### Queue health snapshot

```bash
python manage.py reminder_queue_health
```

Outputs a single JSON line with queue counters and oldest queued age for dashboards/alerts.

### Replay dead-letter reminders

```bash
python manage.py replay_failed_reminders --limit 200 --older-than-minutes 15
```

Re-queues failed reminders in bulk (operational replay).

## Scheduling and alerts

Terraform (`terraform/ops.tf`) schedules the reminder commands with EventBridge:

- `enqueue_reminders` on `var.reminder_enqueue_schedule_expression`
- `process_reminders` on `var.reminder_process_schedule_expression`

CloudWatch alarms:

- `enqueue_reminders` failed invocations
- `process_reminders` failed invocations

## Provider and security settings

Configure in environment:

- `REMINDER_EMAIL_PROVIDER=internal|sendgrid`
- `REMINDER_SMS_PROVIDER=internal|twilio`
- `REMINDER_WEBHOOK_TOKEN=<shared-secret>`
- `REMINDER_SENDGRID_API_KEY`, `REMINDER_SENDGRID_FROM_EMAIL`, `REMINDER_SENDGRID_FROM_NAME`
- `REMINDER_TWILIO_ACCOUNT_SID`, `REMINDER_TWILIO_AUTH_TOKEN`, `REMINDER_TWILIO_FROM_NUMBER`
- `REMINDER_TWILIO_STATUS_CALLBACK_URL` (optional)
- `REMINDER_SENDGRID_WEBHOOK_SECRET` and/or `REMINDER_TWILIO_WEBHOOK_SECRET`

Webhook signature verification supports HMAC SHA256 with:

- `X-Webhook-Timestamp`
- `X-Webhook-Signature`
- signed payload: `<timestamp>.<raw_request_body>`

If provider-specific secret is not configured, endpoint falls back to `REMINDER_WEBHOOK_TOKEN` header validation (`X-Reminder-Webhook-Token`).

## Tests

Run targeted tests:

```bash
pytest apps/reminders/tests/test_reminder_commands.py -v
pytest apps/reminders/tests/test_reminder_api.py -v
```
