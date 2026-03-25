# Scheduling Assistant (Backend MVP)

This document describes the backend-only Scheduling Assistant introduced for clinic workload balancing.

## Objective

Give clinic staff a reliable, explainable API layer to:

- inspect doctor capacity vs booking load,
- identify overload windows early,
- generate deterministic schedule optimization suggestions.

This MVP does not auto-apply changes and does not include frontend UI.

## Endpoints

### 1) Capacity Insights

`GET /api/schedule/capacity-insights/`

Query params:

- `from=YYYY-MM-DD` (optional if `to` omitted)
- `to=YYYY-MM-DD` (optional if `from` omitted)
- `granularity=day|hour` (default: `day`)
- `vet=<id>` (optional)
- `overload_threshold_pct=<float>` (optional, default `85`)

Defaults and limits:

- when `from` and `to` are omitted, backend uses a 14-day window from current local date
- date window cannot exceed 60 days

Response highlights:

- `summary` with total available/booked/utilization and overload count
- `by_vet[]` aggregate load by vet
- `by_day[]` aggregate load by day
- `rows[]` detailed rows (day/hour based on granularity)
- `overload_windows[]`

### 2) Optimization Suggestions

`GET /api/schedule/optimization-suggestions/`

Query params:

- `from=YYYY-MM-DD` (optional if `to` omitted)
- `to=YYYY-MM-DD` (optional if `from` omitted)
- `vet=<id>` (optional)
- `limit=<int>` (default `5`, max `20`)
- `overload_threshold_pct=<float>` (optional, default `85`)

Response highlights:

- `suggestions[]` ranked list containing:
  - `kind` (`reassign_vet` or `move_slot`)
  - `current` and `proposed` schedule fields
  - `reason` (human-readable)
  - `impact_estimate` (minutes shifted + rough overload reduction)
  - `confidence` (rule-based confidence score)

## Permission Model

- Both endpoints require authentication.
- Both use clinic staff permission scope (`IsStaffOrVet` + `HasClinic`).
- All queries are hard-scoped to `request.user.clinic_id`.

## Algorithm (MVP)

### Capacity

For each vet/day in range:

1. Build working intervals:
   - clinic holiday -> no intervals
   - vet exception day-off -> no intervals
   - vet exception custom hours -> one override interval
   - else active `VetWorkingHours` rows for weekday
   - fallback to default config (`DEFAULT_CLINIC_OPEN_TIME`, `DEFAULT_CLINIC_CLOSE_TIME`)
2. Compute available minutes (sum of interval durations).
3. Compute booked minutes from overlapping appointments in active statuses:
   - `scheduled`
   - `confirmed`
   - `checked_in`
4. Calculate utilization and overload flag (`>= overload_threshold_pct`).

### Suggestions

From overloaded vet/day rows:

1. Iterate candidate appointments in deterministic order.
2. Try `reassign_vet` first:
   - same time window
   - candidate vet has working coverage
   - no conflicting appointment for vet
   - no room conflict if appointment has room
3. If no reassignment is possible, try `move_slot`:
   - same vet, same day
   - 30-minute stepping through free intervals
   - no vet/room conflicts
4. Return first ranked matches up to `limit`.

## Explainability Contract

Each suggestion includes enough context for human review:

- what changes (`current` -> `proposed`)
- why it helps (`reason`)
- expected effect (`impact_estimate`)
- confidence score for sorting/prioritization

## Conflict Safety

Suggestion generation already validates:

- overlapping appointment conflicts for vet
- room overlap conflicts when room is assigned
- clinic scope boundary

Because this MVP is read-only, no write race is possible at API level.
If/when a future `apply` endpoint is added, it must repeat these checks atomically inside a transaction.

## Operational Notes

- Hour granularity can produce large payloads on long ranges; keep hourly requests to short windows.
- Use day granularity for dashboards, hour granularity for drill-down.
- If clinics do not configure `VetWorkingHours`, fallback hours are used from settings.

## Known Limitations

- No machine-learning demand forecast (rules-only).
- No notion of vet specialization tags yet.
- No travel/equipment prep buffers between visits.
- No auto-apply endpoint in MVP.

## Testing

Run targeted scheduling assistant tests:

```bash
pytest apps/scheduling/tests/test_scheduling_assistant.py -v
```

Run the full scheduling suite:

```bash
pytest apps/scheduling/tests -v
```
