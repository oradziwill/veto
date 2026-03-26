# Operations API Updates

This note tracks recently added backend operational endpoints/features.

## 1) Visit completion improvements

- `GET /api/appointments/<id>/visit-readiness/`
- `POST /api/appointments/<id>/close-visit/`

Behavior:
- visit closure remains backward compatible by default,
- strict requirement for clinical exam is optional via:
  - `REQUIRE_CLINICAL_EXAM_FOR_VISIT_CLOSE=True`

Reference:
- `VISIT_CLOSE_WORKFLOW.md`

## 2) Cancellation and no-show analytics

- `GET /api/appointments/cancellation-analytics/`

Supports:
- date range filters (`date_from`, `date_to`)
- aggregate sections: totals, by vet, by visit type, by weekday, cancellation source, lead-time buckets
- CSV export:
  - `GET /api/appointments/cancellation-analytics/?export=csv`

## 3) Scheduling assistant API hardening

- `GET /api/schedule/capacity-insights/`
- `GET /api/schedule/optimization-suggestions/`

Enhancements:
- stricter parameter validation (`vet`, `limit`, thresholds),
- safer window limits for hourly granularity,
- payload safety (`rows_limit`, truncation metadata).

Reference:
- `SCHEDULING_ASSISTANT.md`

## 4) Clinic staff management API

- `GET/POST /api/users/`
- `GET/PATCH/DELETE /api/users/<id>/`

Behavior:
- clinic admin only,
- hard clinic scoping,
- role updates keep `is_vet` synchronized for doctor role.

Reference:
- `docs/user-roles.md` (root docs)

## 5) KPI CSV exports

CSV export added to:
- `GET /api/billing/revenue-summary/?export=csv`
- `GET /api/reminders/analytics/?export=csv`
- `GET /api/appointments/cancellation-analytics/?export=csv`
