# Reminder Engine MVP

This document describes the reminder pipeline for appointments, vaccinations, and invoices.

## Scope

- Reminder queue model (`apps.reminders.models.Reminder`)
- Read/resend API (`/api/reminders/`)
- Consent/preferences API (`/api/reminder-preferences/`)
- Provider config API (`/api/reminder-provider-configs/`)
- Template API and preview (`/api/reminder-templates/`, `/api/reminder-templates/preview/`)
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
- `locale` (e.g. `en`, `pl`)
- `quiet_hours_start`, `quiet_hours_end`

`ReminderTemplate` stores clinic-scoped, localized message templates by
`(clinic, reminder_type, channel, locale)`. Templates support placeholders and
are versioned through `ReminderTemplateVersion` snapshots on each create/update.

Supported placeholders:

- `{clinic_name}`
- `{patient_name}`
- `{owner_name}`
- `{appointment_start}`
- `{due_date}`
- `{vaccine_name}`
- `{invoice_number}`

## API

### List reminders

`GET /api/reminders/`

Optional filters:

- `status`
- `type`
- `channel`

### Retrieve reminder

`GET /api/reminders/<id>/`

### Reminder metrics snapshot

`GET /api/reminders/metrics/`

Clinic-scoped mini observability payload:

- status counts (`queued`, `deferred`, `sent`, `failed`, `cancelled`)
- provider counts
- `failed_last_24h`
- `oldest_queued_age_seconds`

### Reminder delivery analytics (admin only)

`GET /api/reminders/analytics/`

Query params:

- `period=monthly|daily` (default: `monthly`)
- `from=YYYY-MM-DD`
- `to=YYYY-MM-DD`
- optional filters: `channel`, `provider`, `type`

Payload includes:

- `totals` (`total`, `sent`, `delivered`, `failed`, `cancelled`)
- `rates` (`delivery_rate`, `failure_rate`)
- `by_period[]` trend rows with `label`, status counts, and `delivery_rate`

This endpoint is clinic-scoped and restricted to clinic admin users.

### Resend reminder (admin only)

`POST /api/reminders/<id>/resend/`

Resend resets attempts/errors and sets status to `queued` with immediate scheduling.

### Reminder preferences

`GET/POST/PATCH /api/reminder-preferences/`

Preferences are clinic-scoped. Client must be an active member of the clinic.

### Reminder templates

`GET/POST/PATCH /api/reminder-templates/`

Templates are clinic-scoped. Write access is admin-only.

### Template preview

`POST /api/reminder-templates/preview/`

Preview accepts either:

- `template_id` (existing template in your clinic), or
- inline `subject_template` + `body_template`

Missing placeholders render as empty strings so preview is non-blocking.

### Reminder provider config

`GET/POST/PATCH /api/reminder-provider-configs/`

Stores clinic-level delivery provider selection:

- `email_provider`: `internal|sendgrid`
- `sms_provider`: `internal|twilio`

Write access is admin-only. When enabling external providers, API validates runtime prerequisites:

- SendGrid: `REMINDER_SENDGRID_API_KEY`, `REMINDER_SENDGRID_FROM_EMAIL`, `REMINDER_SENDGRID_WEBHOOK_SECRET`
- Twilio: `REMINDER_TWILIO_ACCOUNT_SID`, `REMINDER_TWILIO_AUTH_TOKEN`, `REMINDER_TWILIO_FROM_NUMBER`, `REMINDER_TWILIO_WEBHOOK_SECRET`

Delivery resolution uses clinic config when present, otherwise falls back to global environment provider settings.

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
- subject/body are rendered from active localized template (`locale` from `ReminderPreference`) with safe fallback templates

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
Includes `failed_last_24h` and `provider_counts` for fast diagnostics.

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

For ECS deployments, Terraform wires these values from Secrets Manager and task env:

- Secrets: `REMINDER_SENDGRID_API_KEY`, `REMINDER_SENDGRID_WEBHOOK_SECRET`, `REMINDER_TWILIO_ACCOUNT_SID`,
  `REMINDER_TWILIO_AUTH_TOKEN`, `REMINDER_TWILIO_WEBHOOK_SECRET`, `REMINDER_WEBHOOK_TOKEN`
- Plain env: `REMINDER_EMAIL_PROVIDER`, `REMINDER_SMS_PROVIDER`, `REMINDER_SENDGRID_FROM_EMAIL`,
  `REMINDER_SENDGRID_FROM_NAME`, `REMINDER_TWILIO_FROM_NUMBER`, `REMINDER_TWILIO_STATUS_CALLBACK_URL`

## Tests

Run targeted tests:

```bash
pytest apps/reminders/tests/test_reminder_commands.py -v
pytest apps/reminders/tests/test_reminder_api.py -v
pytest apps/reminders/tests/test_reminder_templates.py -v
pytest apps/reminders/tests/test_reminder_delivery_providers.py -v
```
