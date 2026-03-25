# Frontend Handoff: Last 3 Days (Reminders + Scheduling)

This note is for frontend implementation and QA. It summarizes what was shipped in backend/frontend around reminders, and how to use it in UI.

## 1) What Was Delivered

### A. Reminder Ops Health Widget (already in FE)
- Purpose: quick operational visibility of reminder queue health.
- FE files:
  - `src/components/tabs/ReminderOpsHealthWidget.jsx`
  - `src/utils/reminderMetrics.js`
  - `src/components/tabs/OwnerDashboardTab.jsx` (overview placement)
- API:
  - `GET /api/reminders/metrics/`
- Current behavior:
  - auto-refresh every 60s
  - shows status counts, failed (total + 24h), oldest queued age, provider split
  - health state is derived in FE (`healthy`, `degraded`, `unknown`) from thresholds in `src/utils/reminderMetrics.js`

### B. Reminder Analytics + A/B Attribution (already in FE)
- Purpose: trend visibility and copy experiment impact tracking.
- FE files:
  - `src/components/tabs/ReminderAnalyticsPanel.jsx`
  - `src/components/tabs/OwnerDashboardTab.jsx` (`Reminders` subtab)
  - `src/services/api.js` (`remindersAPI.analytics`, `remindersAPI.experimentAttribution`)
- APIs:
  - `GET /api/reminders/analytics/?period=monthly|daily&from=YYYY-MM-DD&to=YYYY-MM-DD&channel=&provider=&type=`
  - `GET /api/reminders/experiment-attribution/?from=YYYY-MM-DD&to=YYYY-MM-DD&channel=&provider=&minimum_sample_size=`
- Current behavior:
  - KPI cards + trend charts
  - variant comparison section for delivery/no-show rates
  - sample-size warning support from backend

### C. Two-Way Reminder Replies (backend delivered, FE queue ready to build)
- Purpose: owners reply to reminders with confirm/cancel/reschedule intents.
- APIs:
  - `POST /api/reminders/replies/<provider>/` (provider webhook, public)
  - `GET /api/reminder-replies/?action_status=needs_review` (staff queue)
- Key backend behavior:
  - parses intents from text
  - appointment status auto-updates for confirm/cancel
  - reschedule/unknown goes to staff follow-up queue
  - idempotent reply processing

### D. Owner Portal Action Links (backend delivered)
- Purpose: one-click self-service from reminder message links.
- API:
  - `GET /api/reminders/portal/<token>/` (preview token/action/reminder)
  - `POST /api/reminders/portal/<token>/` (execute action)
- Actions:
  - `confirm`, `cancel`, `reschedule_request`
- Notes:
  - one-time token usage
  - token expiry enforced
  - links are injected into appointment reminder templates when portal base URL is configured

### E. Automated Reminder Escalation Playbooks (backend delivered)
- Purpose: automatic follow-up/escalation for unresolved situations.
- APIs:
  - `GET/POST/PATCH/DELETE /api/reminder-escalation-rules/` (staff read, admin write)
  - `GET /api/reminder-escalation-executions/?status=applied|skipped`
  - `GET /api/reminder-escalation-metrics/` (admin-only 24h summary)
- Command:
  - `python manage.py run_reminder_escalations`

### F. Scheduling Assistant Backend MVP (backend delivered)
- Purpose: help clinics identify vet overload and receive deterministic schedule optimization suggestions.
- APIs:
  - `GET /api/schedule/capacity-insights/?from=YYYY-MM-DD&to=YYYY-MM-DD&granularity=day|hour&vet=&overload_threshold_pct=`
  - `GET /api/schedule/optimization-suggestions/?from=YYYY-MM-DD&to=YYYY-MM-DD&vet=&limit=&overload_threshold_pct=`
- Key backend behavior:
  - clinic-scoped capacity analytics (available/booked/utilization)
  - overload window detection with configurable threshold
  - ranked suggestions (`reassign_vet` or `move_slot`) with `reason`, `impact_estimate`, `confidence`
  - deterministic and conflict-aware suggestion generation

## 2) How FE Should Use It

## Existing UI (already integrated)
- Keep using:
  - `ReminderOpsHealthWidget` in owner dashboard overview
  - `ReminderAnalyticsPanel` in owner dashboard reminders subtab
- Existing translations are already added in:
  - `src/locales/en.json`
  - `src/locales/pl.json`

## New UI surfaces to implement next

### A. Staff "Unresolved Replies" Inbox
- Endpoint: `GET /api/reminder-replies/?action_status=needs_review`
- Suggested columns:
  - patient, owner/contact, raw reply text, normalized intent, created at, action note
- Suggested actions:
  - mark resolved
  - open linked appointment and assign follow-up

### B. Escalation Rules Admin Screen
- Endpoint set:
  - list/create/edit/delete: `/api/reminder-escalation-rules/`
  - metrics card data: `/api/reminder-escalation-metrics/`
  - run history: `/api/reminder-escalation-executions/`
- Form fields:
  - `name`
  - `trigger_type` (`appointment_unconfirmed`, `reschedule_unresolved`, `invoice_overdue`)
  - `delay_minutes`
  - `action_type` (`enqueue_followup`, `flag_for_review`)
  - `is_active`
  - `max_executions_per_target`

### C. Optional Public Owner Portal Page
- Flow:
  1. FE route receives token from URL.
  2. Call `GET /api/reminders/portal/<token>/` for preview.
  3. Show action confirmation UI.
  4. Call `POST /api/reminders/portal/<token>/`.
  5. Render success/expired/already-used states.

### D. Scheduling Assistant Tab (new FE surface)
- Endpoint set:
  - `/api/schedule/capacity-insights/`
  - `/api/schedule/optimization-suggestions/`
- Suggested sections:
  - utilization summary cards
  - day/hour load table or heatmap
  - suggestion cards with `current` vs `proposed` context
- Suggested filters:
  - date range (`from`, `to`)
  - vet
  - overload threshold
  - granularity (`day`, `hour`)
  - suggestions limit

## 3) FE API Usage Notes

- All clinic-internal endpoints require auth and respect clinic scoping.
- Admin-only endpoints:
  - `/api/reminder-escalation-metrics/`
  - writes on `/api/reminder-escalation-rules/`
- Scheduling assistant endpoints are staff-readable (doctor/receptionist/admin), auth required.
- Webhook and portal token endpoints are public by design.

## 4) QA Checklist For Frontend

- Ops widget refreshes and changes state correctly under mocked thresholds.
- Analytics filters update charts and KPI cards.
- Attribution section renders warning for small sample.
- Replies inbox default filter is unresolved (`needs_review`).
- Escalation rules CRUD validates positive values for delay and max executions.
- Portal token page handles invalid/expired/used token states cleanly.
- Capacity insights handles default 14-day window when `from`/`to` are not passed.
- Scheduling filters handle invalid date ranges and invalid granularity threshold inputs.
- Suggestion cards render both move and reassignment variants.

## 5) Quick Next Sprint FE Scope

- Build `ReminderRepliesInboxTab` for staff follow-up.
- Build `ReminderEscalationRulesTab` for clinic admins.
- Build `SchedulingAssistantTab` for workload and suggestion visibility.
- Add role-based navigation gating for new tabs.
- Add lightweight frontend tests for filters, error states, and empty states.
