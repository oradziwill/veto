export const DEFAULT_REMINDER_HEALTH_THRESHOLDS = {
  warnFailedLast24h: 1,
  warnOldestQueuedAgeSeconds: 1800, // 30 minutes
  warnQueuedCount: 20,
}

export function getReminderHealthState(payload, thresholds = DEFAULT_REMINDER_HEALTH_THRESHOLDS) {
  if (!payload || typeof payload !== "object") {
    return "unknown"
  }
  const failedLast24h = Number(payload.failed_last_24h || 0)
  const oldestQueuedAgeSeconds = Number(payload.oldest_queued_age_seconds || 0)
  const queued = Number(payload?.status_counts?.queued || 0)

  if (
    failedLast24h >= thresholds.warnFailedLast24h ||
    oldestQueuedAgeSeconds >= thresholds.warnOldestQueuedAgeSeconds ||
    queued >= thresholds.warnQueuedCount
  ) {
    return "degraded"
  }
  return "healthy"
}

export function formatDurationShort(totalSeconds) {
  const seconds = Math.max(0, Number(totalSeconds || 0))
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const remMinutes = minutes % 60
  if (hours < 24) return remMinutes > 0 ? `${hours}h ${remMinutes}m` : `${hours}h`
  const days = Math.floor(hours / 24)
  const remHours = hours % 24
  return remHours > 0 ? `${days}d ${remHours}h` : `${days}d`
}
