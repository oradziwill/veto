# Billing: Recording payments and auto-closing invoices

## Overview

- **Endpoint:** `POST /api/billing/invoices/<id>/payments/`
- Records a payment (amount, method, paid_at, note) against an invoice.
- After each payment, **balance_due** is recalculated (derived from invoice total minus completed payments).
- When **balance_due** reaches zero, the invoice **status** is set to `paid` automatically.
- The response is the **updated invoice** (with `balance_due`, `status`, `payments`), not only the new payment.

## Request / response

**POST** body example:

```json
{
  "amount": "150.00",
  "method": "cash",
  "status": "completed",
  "paid_at": "2026-03-11T12:00:00Z",
  "note": "Optional note"
}
```

**Response (201):** Full invoice object (same shape as `GET /api/billing/invoices/<id>/`), including updated `balance_due`, `status`, and the `payments` list.

## Running tests

From the **backend** directory (with venv activated):

```bash
# Billing + payment behavior
pytest apps/billing/tests/test_invoices.py tests/behavior/test_visit_to_invoice_workflow.py -v

# All behavior tests
pytest tests/behavior/ -v

# Full test suite
pytest
```

Relevant tests:

- `test_record_payment` – full payment returns invoice with status paid, balance_due 0.
- `test_record_partial_payment_returns_invoice_with_updated_balance_due` – partial payment returns updated balance, status not paid.
- `test_record_final_payment_that_settles_invoice_returns_paid_invoice` – second payment settles invoice; response has status paid, balance_due 0.
- `test_partial_payment_keeps_invoice_sent_until_fully_paid` – two partial payments; API returns updated invoice after each; invoice becomes paid after the second.

## Marking overdue invoices (scheduled job)

The management command **`mark_overdue_invoices`** sets `status` to `overdue` for invoices that are `status='sent'` and have `due_date < today` (and a non-null `due_date`). Run it periodically so overdue invoices are updated automatically.

**Run (from backend directory, or with `DJANGO_SETTINGS_MODULE=config.settings` set):**

```bash
python manage.py mark_overdue_invoices
```

**Deployment:** Schedule this command daily (e.g. cron at 01:00, an ECS scheduled task, or a GitHub Actions scheduled workflow). Example cron: `0 1 * * * cd /app/backend && python manage.py mark_overdue_invoices`. Running once per day (e.g. early morning) keeps timezone handling simple and load minimal.

**Relevant tests:** `apps/billing/tests/test_mark_overdue_invoices.py` – command runs on empty DB; only sent + past-due updated; count logged; sent with null `due_date` unchanged.
