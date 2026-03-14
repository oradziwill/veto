# Reminder Engine MVP

This document describes the first backend reminder pipeline for appointments, vaccinations, and invoices.

## Scope

- Reminder queue model (`apps.reminders.models.Reminder`)
- Read/resend API (`/api/reminders/`)
- Queue hydration command (`enqueue_reminders`)
- Delivery processing command (`process_reminders`)
- Delivery channel abstraction with provider-agnostic placeholders (`email`, `sms`)

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

### Process queue

```bash
python manage.py process_reminders
python manage.py process_reminders --limit 200 --retry-minutes 10
```

Behavior:

- sends queued reminders with `scheduled_for <= now`
- on success: marks `sent`
- on failure: increments attempts and either re-queues (`queued`) or terminally fails (`failed`) when attempts reach `max_attempts`

## Tests

Run targeted tests:

```bash
pytest apps/reminders/tests/test_reminder_commands.py -v
pytest apps/reminders/tests/test_reminder_api.py -v
```
