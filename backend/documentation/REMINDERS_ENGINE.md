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
- Escalation playbook command (`run_reminder_escalations`)
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
- `experiment_key`, `experiment_variant` (for A/B attribution)

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
- `{confirm_url}` (appointment reminders, when portal base URL configured)
- `{cancel_url}` (appointment reminders, when portal base URL configured)
- `{reschedule_url}` (appointment reminders, when portal base URL configured)

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

### Reminder experiment attribution (admin only)

`GET /api/reminders/experiment-attribution/`

Query params:

- `from=YYYY-MM-DD`
- `to=YYYY-MM-DD`
- optional filters: `channel`, `provider`
- `minimum_sample_size` (default: `30`)

Returns variant-level attribution rows for appointment reminders:

- reminder volume and delivery rate
- appointment outcomes (`completed`, `cancelled`, `no_show`)
- `no_show_rate` per variant
- `sample_warning` when appointments are below minimum sample threshold

Current deterministic experiment assignment is `appointment_copy_v1` with variants `A` and `B`.

### Inbound owner replies (two-way reminders)

`POST /api/reminders/replies/<provider>/`

Supported intent parsing from reply text:

- `confirm` (e.g. `YES`, `confirm`, `tak`)
- `cancel` (e.g. `NO`, `cancel`, `odwołaj`)
- `reschedule` (e.g. `reschedule`, `zmień termin`)
- fallback `unknown`

Behavior:

- idempotent processing keyed by `(provider, provider_reply_id)`
- for appointment reminders:
  - `confirm` -> appointment status `confirmed` when schedulable
  - `cancel` -> appointment status `cancelled` when schedulable
  - `reschedule` / `unknown` -> unresolved queue item for staff follow-up
- every processed reply creates `ReminderEvent(event_type=reply_received)`

### Inbound reply staff queue

`GET /api/reminder-replies/`

Clinic-scoped staff endpoint with unresolved items by default (`action_status=needs_review`).
Use `?action_status=` to inspect all reply outcomes (`applied`, `needs_review`, `ignored`).

### Owner portal action links

`GET/POST /api/reminders/portal/<token>/`

Tokenized, unauthenticated owner action endpoint for reminder self-service:

- `confirm`
- `cancel`
- `reschedule_request`

Token behavior:

- signed payload with expiry (`REMINDER_PORTAL_TOKEN_TTL_HOURS`)
- database-backed one-time usage guard (`used_at`)
- strict action/reminder binding

Execution rules:

- `confirm` / `cancel`: update linked appointment if transition is valid
- `reschedule_request`: creates unresolved staff follow-up item
- each execution writes reminder event audit payload (`source=owner_portal`)

### Escalation playbooks

`GET/POST/PATCH/DELETE /api/reminder-escalation-rules/`

Clinic-scoped rule CRUD:

- trigger types: `appointment_unconfirmed`, `reschedule_unresolved`, `invoice_overdue`
- action types: `enqueue_followup`, `flag_for_review`
- guardrails: `is_active`, `delay_minutes`, `max_executions_per_target`
- write access is clinic-admin only

`GET /api/reminder-escalation-executions/`

Read-only execution log for staff/admin with optional `?status=applied|skipped`.

`GET /api/reminder-escalation-metrics/` (admin only)

24h ops payload:

- `triggered_total`
- `applied_total`
- `skipped_total`
- `by_rule[]`

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

### Run escalation playbooks

```bash
python manage.py run_reminder_escalations
python manage.py run_reminder_escalations --clinic-id 12 --limit 200
```

Behavior:

- evaluates active clinic rules against reminder/reply/invoice state
- enforces idempotency via `(rule, reminder)` execution uniqueness
- enforces target guardrail (`max_executions_per_target`)
- writes `ReminderEscalationExecution` audit rows and `ReminderEvent(event_type=escalated)`

### Replay dead-letter reminders

```bash
python manage.py replay_failed_reminders --limit 200 --older-than-minutes 15
```

Re-queues failed reminders in bulk (operational replay).

## Scheduling and alerts

Terraform (`terraform/ops.tf`) schedules the reminder commands with EventBridge:

- `enqueue_reminders` on `var.reminder_enqueue_schedule_expression`
- `process_reminders` on `var.reminder_process_schedule_expression`
- `run_reminder_escalations` (recommended every 5-15 minutes)

CloudWatch alarms:

- `enqueue_reminders` failed invocations
- `process_reminders` failed invocations
- `run_reminder_escalations` failed invocations

## Provider and security settings

Configure in environment:

- `REMINDER_EMAIL_PROVIDER=internal|sendgrid`
- `REMINDER_SMS_PROVIDER=internal|twilio`
- `REMINDER_WEBHOOK_TOKEN=<shared-secret>`
- `REMINDER_SENDGRID_API_KEY`, `REMINDER_SENDGRID_FROM_EMAIL`, `REMINDER_SENDGRID_FROM_NAME`
- `REMINDER_TWILIO_ACCOUNT_SID`, `REMINDER_TWILIO_AUTH_TOKEN`, `REMINDER_TWILIO_FROM_NUMBER`
- `REMINDER_TWILIO_STATUS_CALLBACK_URL` (optional)
- `REMINDER_SENDGRID_WEBHOOK_SECRET` and/or `REMINDER_TWILIO_WEBHOOK_SECRET`
- `REMINDER_PORTAL_BASE_URL` (e.g. frontend/base host for link generation)
- `REMINDER_PORTAL_TOKEN_TTL_HOURS` (default `72`)

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
