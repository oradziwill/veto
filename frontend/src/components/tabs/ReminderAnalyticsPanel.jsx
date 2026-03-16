import { useEffect, useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { remindersAPI } from "../../services/api"

const CARD = {
  background: "white",
  borderRadius: "12px",
  padding: "1.5rem",
  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
}

const fmtPct = (n) => `${(Number(n || 0) * 100).toFixed(1)}%`

const toDateInput = (d) => d.toISOString().slice(0, 10)

export default function ReminderAnalyticsPanel() {
  const { t } = useTranslation()
  const today = useMemo(() => new Date(), [])
  const initialFrom = useMemo(() => {
    const d = new Date(today)
    d.setMonth(d.getMonth() - 5)
    d.setDate(1)
    return toDateInput(d)
  }, [today])
  const initialTo = useMemo(() => toDateInput(today), [today])

  const [period, setPeriod] = useState("monthly")
  const [fromDate, setFromDate] = useState(initialFrom)
  const [toDate, setToDate] = useState(initialTo)
  const [channel, setChannel] = useState("")
  const [provider, setProvider] = useState("")
  const [type, setType] = useState("")

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [data, setData] = useState(null)

  const load = async () => {
    try {
      setLoading(true)
      setError("")
      const res = await remindersAPI.analytics({
        period,
        from: fromDate,
        to: toDate,
        channel: channel || undefined,
        provider: provider || undefined,
        type: type || undefined,
      })
      setData(res.data)
    } catch {
      setError(t("ownerDashboard.reminderAnalytics.loadError"))
    } finally {
      setLoading(false)
    }
  }

  const rows = data?.by_period || []
  const totals = data?.totals || {}
  const rates = data?.rates || {}

  useEffect(() => {
    load()
    // load on initial render with default filters
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div style={CARD}>
        <h3 style={{ margin: "0 0 0.75rem", fontSize: "1rem", fontWeight: 600, color: "#2d3748" }}>
          {t("ownerDashboard.reminderAnalytics.title")}
        </h3>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(6, minmax(0, 1fr))",
            gap: "0.75rem",
            alignItems: "end",
          }}
        >
          <Filter label={t("ownerDashboard.reminderAnalytics.period")}>
            <select value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="monthly">{t("ownerDashboard.reminderAnalytics.monthly")}</option>
              <option value="daily">{t("ownerDashboard.reminderAnalytics.daily")}</option>
            </select>
          </Filter>
          <Filter label={t("ownerDashboard.reminderAnalytics.from")}>
            <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          </Filter>
          <Filter label={t("ownerDashboard.reminderAnalytics.to")}>
            <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          </Filter>
          <Filter label={t("ownerDashboard.reminderAnalytics.channel")}>
            <select value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="">{t("ownerDashboard.reminderAnalytics.all")}</option>
              <option value="email">email</option>
              <option value="sms">sms</option>
            </select>
          </Filter>
          <Filter label={t("ownerDashboard.reminderAnalytics.provider")}>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="">{t("ownerDashboard.reminderAnalytics.all")}</option>
              <option value="internal">internal</option>
              <option value="sendgrid">sendgrid</option>
              <option value="twilio">twilio</option>
            </select>
          </Filter>
          <Filter label={t("ownerDashboard.reminderAnalytics.type")}>
            <select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">{t("ownerDashboard.reminderAnalytics.all")}</option>
              <option value="appointment">appointment</option>
              <option value="vaccination">vaccination</option>
              <option value="invoice">invoice</option>
            </select>
          </Filter>
        </div>
        <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem" }}>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            style={{
              border: "none",
              background: "#48bb78",
              color: "white",
              padding: "0.45rem 0.9rem",
              borderRadius: "6px",
              cursor: loading ? "default" : "pointer",
              fontWeight: 600,
            }}
          >
            {loading ? t("common.loading") : t("ownerDashboard.reminderAnalytics.apply")}
          </button>
        </div>
        {error && (
          <p style={{ marginTop: "0.65rem", color: "#c53030", fontSize: "0.9rem" }}>
            {error}
          </p>
        )}
      </div>

      {data && (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
              gap: "0.8rem",
            }}
          >
            <Stat value={totals.total || 0} label={t("ownerDashboard.reminderAnalytics.total")} />
            <Stat value={totals.delivered || 0} label={t("ownerDashboard.reminderAnalytics.delivered")} />
            <Stat value={totals.failed || 0} label={t("ownerDashboard.reminderAnalytics.failed")} />
            <Stat value={fmtPct(rates.delivery_rate)} label={t("ownerDashboard.reminderAnalytics.deliveryRate")} />
          </div>

          <div style={CARD}>
            <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", fontWeight: 600, color: "#2d3748" }}>
              {t("ownerDashboard.reminderAnalytics.volumeTrend")}
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="total" name={t("ownerDashboard.reminderAnalytics.total")} fill="#63b3ed" />
                <Bar dataKey="delivered" name={t("ownerDashboard.reminderAnalytics.delivered")} fill="#48bb78" />
                <Bar dataKey="failed" name={t("ownerDashboard.reminderAnalytics.failed")} fill="#fc8181" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={CARD}>
            <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", fontWeight: 600, color: "#2d3748" }}>
              {t("ownerDashboard.reminderAnalytics.deliveryRateTrend")}
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} domain={[0, 1]} tickFormatter={fmtPct} />
                <Tooltip formatter={(v) => fmtPct(v)} />
                <Line
                  type="monotone"
                  dataKey="delivery_rate"
                  stroke="#2b6cb0"
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}

function Filter({ label, children }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
      <span style={{ fontSize: "0.75rem", color: "#718096", fontWeight: 600 }}>
        {label}
      </span>
      <div
        style={{
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          overflow: "hidden",
          background: "white",
        }}
      >
        {children}
      </div>
    </label>
  )
}

function Stat({ value, label }) {
  return (
    <div
      style={{
        border: "1px solid #edf2f7",
        borderRadius: "8px",
        padding: "0.7rem 0.8rem",
        background: "#f8fafc",
      }}
    >
      <div style={{ fontSize: "1rem", fontWeight: 700, color: "#2d3748" }}>{value}</div>
      <div style={{ fontSize: "0.75rem", color: "#718096", marginTop: "0.1rem" }}>{label}</div>
    </div>
  )
}
