import { useEffect, useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import { remindersAPI } from "../../services/api"
import {
  formatDurationShort,
  getReminderHealthState,
} from "../../utils/reminderMetrics"

const CARD = {
  background: "white",
  borderRadius: "12px",
  padding: "1.5rem",
  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
}

const STATUS_META = {
  healthy: { color: "#276749", bg: "#f0fff4" },
  degraded: { color: "#9b2c2c", bg: "#fff5f5" },
  unknown: { color: "#2b6cb0", bg: "#ebf8ff" },
}

const toCount = (n) => Number(n || 0)

export default function ReminderOpsHealthWidget({ refreshMs = 60000 }) {
  const { t } = useTranslation()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const loadMetrics = async () => {
    try {
      setError("")
      const res = await remindersAPI.metrics()
      setData(res.data)
    } catch {
      setError(t("ownerDashboard.reminderOps.loadError"))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let mounted = true
    const run = async () => {
      if (!mounted) return
      await loadMetrics()
    }
    run()
    const id = setInterval(run, refreshMs)
    return () => {
      mounted = false
      clearInterval(id)
    }
  }, [refreshMs])

  const state = useMemo(() => getReminderHealthState(data), [data])
  const stateMeta = STATUS_META[state] || STATUS_META.unknown
  const statusCounts = data?.status_counts || {}
  const providerCounts = data?.provider_counts || {}

  return (
    <div style={CARD}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600, color: "#2d3748" }}>
          {t("ownerDashboard.reminderOps.title")}
        </h3>
        <span
          style={{
            padding: "0.25rem 0.6rem",
            borderRadius: "999px",
            fontSize: "0.75rem",
            fontWeight: 700,
            color: stateMeta.color,
            background: stateMeta.bg,
          }}
        >
          {t(`ownerDashboard.reminderOps.state.${state}`)}
        </span>
      </div>

      {loading && <p style={{ marginTop: "0.75rem", color: "#718096" }}>{t("common.loading")}</p>}

      {!loading && error && (
        <div
          style={{
            marginTop: "0.75rem",
            borderRadius: "8px",
            background: "#fff5f5",
            color: "#c53030",
            padding: "0.75rem",
            fontSize: "0.9rem",
          }}
        >
          <div>{error}</div>
          <button
            type="button"
            onClick={loadMetrics}
            style={{
              marginTop: "0.5rem",
              border: "none",
              background: "#48bb78",
              color: "white",
              padding: "0.35rem 0.7rem",
              borderRadius: "6px",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            {t("common.retry")}
          </button>
        </div>
      )}

      {!loading && !error && data && (
        <>
          <div
            style={{
              marginTop: "0.9rem",
              display: "grid",
              gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
              gap: "0.65rem",
            }}
          >
            <Stat value={toCount(statusCounts.queued)} label={t("ownerDashboard.reminderOps.queued")} />
            <Stat value={toCount(statusCounts.failed)} label={t("ownerDashboard.reminderOps.failed")} />
            <Stat
              value={toCount(data.failed_last_24h)}
              label={t("ownerDashboard.reminderOps.failedLast24h")}
            />
            <Stat
              value={formatDurationShort(data.oldest_queued_age_seconds)}
              label={t("ownerDashboard.reminderOps.oldestQueuedAge")}
            />
          </div>

          <div
            style={{
              marginTop: "0.85rem",
              fontSize: "0.82rem",
              color: "#4a5568",
              display: "flex",
              gap: "1rem",
              flexWrap: "wrap",
            }}
          >
            <span>{t("ownerDashboard.reminderOps.providers.internal")}: {toCount(providerCounts.internal)}</span>
            <span>{t("ownerDashboard.reminderOps.providers.sendgrid")}: {toCount(providerCounts.sendgrid)}</span>
            <span>{t("ownerDashboard.reminderOps.providers.twilio")}: {toCount(providerCounts.twilio)}</span>
          </div>
        </>
      )}
    </div>
  )
}

function Stat({ value, label }) {
  return (
    <div
      style={{
        border: "1px solid #edf2f7",
        borderRadius: "8px",
        padding: "0.6rem 0.7rem",
        background: "#f8fafc",
      }}
    >
      <div style={{ fontSize: "1rem", fontWeight: 700, color: "#2d3748" }}>{value}</div>
      <div style={{ fontSize: "0.72rem", color: "#718096", marginTop: "0.1rem" }}>{label}</div>
    </div>
  )
}
