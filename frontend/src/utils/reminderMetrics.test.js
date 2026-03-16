import test from "node:test"
import assert from "node:assert/strict"

import {
  formatDurationShort,
  getReminderHealthState,
} from "./reminderMetrics.js"

test("getReminderHealthState returns unknown for empty payload", () => {
  assert.equal(getReminderHealthState(null), "unknown")
})

test("getReminderHealthState returns healthy for low metrics", () => {
  const payload = {
    failed_last_24h: 0,
    oldest_queued_age_seconds: 120,
    status_counts: { queued: 2 },
  }
  assert.equal(getReminderHealthState(payload), "healthy")
})

test("getReminderHealthState returns degraded on threshold breach", () => {
  const payload = {
    failed_last_24h: 2,
    oldest_queued_age_seconds: 120,
    status_counts: { queued: 2 },
  }
  assert.equal(getReminderHealthState(payload), "degraded")
})

test("formatDurationShort formats seconds/minutes/hours/days", () => {
  assert.equal(formatDurationShort(45), "45s")
  assert.equal(formatDurationShort(180), "3m")
  assert.equal(formatDurationShort(3900), "1h 5m")
  assert.equal(formatDurationShort(90000), "1d 1h")
})
