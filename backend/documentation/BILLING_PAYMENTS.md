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

## Revenue summary (owner dashboard)

- **Endpoint:** `GET /api/billing/revenue-summary/`
- **Permission:** Clinic Admin only (role `admin`). Returns 403 for non-admin staff.
- **Purpose:** Summary of revenue over time for the authenticated user's clinic (invoiced, paid, outstanding, and breakdown by period).

**Query parameters:**

- **period** – Optional. `monthly` (default) or `daily`. Groups totals by month or by day. Invalid value returns 400.
- **from** – Optional. Start of range, ISO date `YYYY-MM-DD`. Default: first day of the current year (or, when `breakdown=monthly` and no `from`/`to`, start of the first month in the trailing window).
- **to** – Optional. End of range, ISO date `YYYY-MM-DD`. Default: today (or last day of current month when using default breakdown window).
- **breakdown** – Optional. `monthly` to include a **monthly** array in the response (for chart data). Any other value returns 400. Omit for standard summary only.
- **months** – Optional. Only valid when `breakdown=monthly`. Positive integer; when `breakdown=monthly` and `from`/`to` are not provided, the range is the last **N** calendar months (default **6**). Invalid or non-positive returns 400. If provided without `breakdown=monthly`, returns 400.

**Response (200):**

Standard response (no breakdown):

```json
{
  "period": "monthly",
  "from": "2026-01-01",
  "to": "2026-03-31",
  "total_invoiced": "4500.00",
  "total_paid": "3800.00",
  "total_outstanding": "700.00",
  "by_period": [
    { "label": "2026-01", "invoiced": "1200.00", "paid": "1200.00" },
    { "label": "2026-02", "invoiced": "1800.00", "paid": "1600.00" },
    { "label": "2026-03", "invoiced": "1500.00", "paid": "1000.00" }
  ]
}
```

With `?breakdown=monthly` the response also includes **monthly** (chart-friendly):

```json
{
  "period": "monthly",
  "from": "2026-01-01",
  "to": "2026-03-31",
  "total_invoiced": "4500.00",
  "total_paid": "3800.00",
  "total_outstanding": "700.00",
  "by_period": [ ... ],
  "monthly": [
    { "month": "2026-01", "revenue": "1200.00", "invoice_count": 8 },
    { "month": "2026-02", "revenue": "1800.00", "invoice_count": 12 },
    { "month": "2026-03", "revenue": "1500.00", "invoice_count": 10 }
  ]
}
```

- **total_invoiced** – Sum of (non-cancelled) invoice line totals with `created_at` in the date range.
- **total_paid** – Sum of completed payments with `paid_at` in the date range.
- **total_outstanding** – `total_invoiced - total_paid`.
- **by_period** – One entry per period in range. **label**: `YYYY-MM` for monthly, `YYYY-MM-DD` for daily. **invoiced** / **paid**: amounts for that period (strings with two decimals).
- **monthly** – Present only when `breakdown=monthly`. One entry per month in range: **month** (`YYYY-MM`), **revenue** (invoiced amount as string), **invoice_count** (non-cancelled invoices in that month). Clinic-scoped.

**Running revenue summary tests:**

```bash
pytest apps/billing/tests/test_revenue_summary.py -v
```

Relevant tests: `test_revenue_summary_admin_only`, `test_revenue_summary_scoped_to_clinic`, `test_revenue_summary_totals`, `test_revenue_summary_by_period_monthly`, `test_revenue_summary_by_period_daily`, `test_revenue_summary_excludes_cancelled`, `test_revenue_summary_invalid_period`, `test_revenue_summary_breakdown_monthly_returns_monthly_array`, `test_revenue_summary_breakdown_monthly_custom_months`, `test_revenue_summary_months_without_breakdown_returns_400`, `test_revenue_summary_invalid_months_returns_400`, `test_revenue_summary_invalid_breakdown_returns_400`, `test_revenue_summary_breakdown_monthly_excludes_cancelled`, `test_revenue_summary_no_breakdown_omits_monthly_key`.
