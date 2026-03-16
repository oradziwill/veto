import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie,
} from 'recharts'
import { invoicesAPI, servicesAPI, clientsAPI, patientsAPI, appointmentsAPI } from '../../services/api'
import ReminderOpsHealthWidget from './ReminderOpsHealthWidget'
import './Tabs.css'

// ── helpers ──────────────────────────────────────────────────────────────────

const CARD = { background: 'white', borderRadius: '12px', padding: '1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }
const SEC_LABEL = { fontSize: '0.75rem', fontWeight: '600', color: '#718096', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }
const CHART_TITLE = { margin: '0 0 1.25rem', fontSize: '1rem', fontWeight: '600', color: '#2d3748' }

const COLORS = { completed: '#48bb78', cancelled: '#fc8181', no_show: '#f6ad55', scheduled: '#63b3ed', confirmed: '#4299e1', checked_in: '#9f7aea' }
const PIE_COLORS = ['#48bb78', '#63b3ed', '#f6ad55', '#fc8181', '#9f7aea', '#76e4f7']
const DAYS_PL = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'Sb', 'Nd']
const DAYS_EN = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const fmt = (n) => Number(n).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const monthLabel = (date) => date.toLocaleString('pl-PL', { month: 'short', year: '2-digit' })

// Build array of N last months (oldest first)
const lastNMonths = (n) => Array.from({ length: n }, (_, i) => {
  const d = new Date()
  d.setDate(1)
  d.setMonth(d.getMonth() - (n - 1 - i))
  return { start: new Date(d.getFullYear(), d.getMonth(), 1), end: new Date(d.getFullYear(), d.getMonth() + 1, 1), label: monthLabel(d) }
})

const StatCard = ({ value, label, color }) => (
  <div className="stat-card">
    <div className="stat-value" style={{ color: color || '#2d3748' }}>{value}</div>
    <div className="stat-label">{label}</div>
  </div>
)

const SubTabNav = ({ tabs, active, onChange }) => (
  <div style={{ display: 'flex', gap: '0.25rem', borderBottom: '2px solid #e2e8f0', marginBottom: '1.5rem' }}>
    {tabs.map(tab => (
      <button
        key={tab.id}
        onClick={() => onChange(tab.id)}
        style={{
          padding: '0.6rem 1.1rem',
          border: 'none',
          background: 'none',
          cursor: 'pointer',
          fontSize: '0.9rem',
          fontWeight: active === tab.id ? '600' : '400',
          color: active === tab.id ? '#276749' : '#718096',
          borderBottom: active === tab.id ? '2px solid #48bb78' : '2px solid transparent',
          marginBottom: '-2px',
          borderRadius: '0',
        }}
      >
        {tab.label}
      </button>
    ))}
  </div>
)

// ── main component ────────────────────────────────────────────────────────────

const OwnerDashboardTab = () => {
  const { t, i18n } = useTranslation()
  const [activeTab, setActiveTab] = useState('overview')
  const [invoices, setInvoices] = useState([])
  const [serviceMap, setServiceMap] = useState({})
  const [clients, setClients] = useState([])
  const [patients, setPatients] = useState([])
  const [appointments, setAppointments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError(null)
        const sixMonthsAgo = new Date()
        sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 5)
        sixMonthsAgo.setDate(1)

        const [invRes, svcRes, clientRes, patientRes, apptRes] = await Promise.all([
          invoicesAPI.list(),
          servicesAPI.list(),
          clientsAPI.inMyClinic(),
          patientsAPI.list(),
          appointmentsAPI.list({ from: sixMonthsAgo.toISOString().slice(0, 10) }),
        ])
        const map = {}
        ;(svcRes.data.results || svcRes.data).forEach(s => { map[s.id] = s.name })
        setInvoices(invRes.data.results || invRes.data)
        setServiceMap(map)
        setClients(clientRes.data.results || clientRes.data)
        setPatients(patientRes.data.results || patientRes.data)
        setAppointments(apptRes.data.results || apptRes.data)
      } catch {
        setError(t('ownerDashboard.loadError'))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const now = new Date()
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
  const months6 = lastNMonths(6)

  // ── overview stats ──────────────────────────────────────────────────────────

  const apptThisMonth = appointments.filter(a => new Date(a.starts_at) >= monthStart)
  const completedThisMonth = apptThisMonth.filter(a => a.status === 'completed').length
  const upcomingCount = appointments.filter(a => new Date(a.starts_at) > now && ['scheduled', 'confirmed'].includes(a.status)).length
  const cancelledNoShow = apptThisMonth.filter(a => ['cancelled', 'no_show'].includes(a.status)).length
  const newPatientsThisMonth = patients.filter(p => new Date(p.created_at) >= monthStart).length
  const revenueThisMonth = invoices
    .filter(inv => inv.status !== 'cancelled' && new Date(inv.created_at) >= monthStart)
    .reduce((sum, inv) => sum + parseFloat(inv.total || 0), 0)
  const outstanding = invoices.filter(inv => ['sent', 'overdue'].includes(inv.status))
  const outstandingAmount = outstanding.reduce((sum, inv) => sum + parseFloat(inv.balance_due || 0), 0)

  const serviceRevenue = {}
  invoices.forEach(inv => {
    ;(inv.lines || []).forEach(line => {
      const key = line.service ? serviceMap[line.service] || `#${line.service}` : line.description
      if (!key) return
      serviceRevenue[key] = (serviceRevenue[key] || 0) + parseFloat(line.line_total || 0)
    })
  })
  const topServices = Object.entries(serviceRevenue).sort((a, b) => b[1] - a[1]).slice(0, 5)
  const maxRevenue = topServices[0]?.[1] || 1

  // ── visit charts ────────────────────────────────────────────────────────────

  const visitsByMonth = months6.map(({ start, end, label }) => {
    const slice = appointments.filter(a => { const s = new Date(a.starts_at); return s >= start && s < end })
    return {
      label,
      [t('ownerDashboard.completed')]: slice.filter(a => a.status === 'completed').length,
      [t('ownerDashboard.cancelled')]: slice.filter(a => a.status === 'cancelled').length,
      [t('ownerDashboard.noShow')]: slice.filter(a => a.status === 'no_show').length,
    }
  })

  const visitStatusPie = Object.entries(
    apptThisMonth.reduce((acc, a) => { acc[a.status] = (acc[a.status] || 0) + 1; return acc }, {})
  ).map(([name, value], i) => ({ name: t(`ownerDashboard.apptStatus.${name}`) || name, value, fill: PIE_COLORS[i % PIE_COLORS.length] }))

  const dayLabels = i18n.language?.startsWith('pl') ? DAYS_PL : DAYS_EN
  const visitsByWeekday = dayLabels.map((day, i) => ({
    day,
    [t('ownerDashboard.visits')]: appointments.filter(a => {
      const d = new Date(a.starts_at).getDay()
      return ((d + 6) % 7) === i && a.status === 'completed'
    }).length,
  }))

  // ── revenue charts ──────────────────────────────────────────────────────────

  const revenueByMonth = months6.map(({ start, end, label }) => ({
    label,
    [t('ownerDashboard.invoiced')]: invoices
      .filter(inv => inv.status !== 'cancelled' && new Date(inv.created_at) >= start && new Date(inv.created_at) < end)
      .reduce((s, inv) => s + parseFloat(inv.total || 0), 0),
    [t('ownerDashboard.paid')]: invoices
      .filter(inv => inv.status === 'paid' && new Date(inv.created_at) >= start && new Date(inv.created_at) < end)
      .reduce((s, inv) => s + parseFloat(inv.total || 0), 0),
  }))

  const invoiceStatusPie = Object.entries(
    invoices.reduce((acc, inv) => { acc[inv.status] = (acc[inv.status] || 0) + 1; return acc }, {})
  ).map(([name, value], i) => ({ name: t(`billing.status.${name}`) || name, value, fill: PIE_COLORS[i % PIE_COLORS.length] }))

  // ── patient charts ──────────────────────────────────────────────────────────

  const allMonths6 = lastNMonths(6)
  const patientsByMonth = allMonths6.map(({ start, end, label }) => ({
    label,
    [t('ownerDashboard.newPatients')]: patients.filter(p => { const d = new Date(p.created_at); return d >= start && d < end }).length,
    [t('ownerDashboard.newClients')]: clients.filter(c => { const d = new Date(c.created_at); return d >= start && d < end }).length,
  }))

  const speciesPie = Object.entries(
    patients.reduce((acc, p) => { const s = p.species || 'other'; acc[s] = (acc[s] || 0) + 1; return acc }, {})
  ).sort((a, b) => b[1] - a[1]).map(([name, value], i) => ({ name, value, fill: PIE_COLORS[i % PIE_COLORS.length] }))

  // ── render ──────────────────────────────────────────────────────────────────

  const subTabs = [
    { id: 'overview', label: t('ownerDashboard.tabOverview') },
    { id: 'visits', label: t('ownerDashboard.tabVisits') },
    { id: 'revenue', label: t('ownerDashboard.tabRevenue') },
    { id: 'patients', label: t('ownerDashboard.tabPatients') },
  ]

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>{t('ownerDashboard.title')}</h2>
        <span style={{ fontSize: '0.85rem', color: '#718096' }}>
          {now.toLocaleString('pl-PL', { month: 'long', year: 'numeric' })}
        </span>
      </div>

      <div className="tab-content-wrapper">
        {loading && <div className="loading-message">{t('common.loading')}</div>}
        {error && <div className="error-message">{error}</div>}

        {!loading && !error && (
          <>
            <SubTabNav tabs={subTabs} active={activeTab} onChange={setActiveTab} />

            {/* ── OVERVIEW ── */}
            {activeTab === 'overview' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <ReminderOpsHealthWidget />
                <div>
                  <div style={SEC_LABEL}>{t('ownerDashboard.sectionClinic')}</div>
                  <div className="inventory-stats">
                    <StatCard value={clients.length} label={t('ownerDashboard.totalClients')} />
                    <StatCard value={patients.length} label={t('ownerDashboard.totalPatients')} />
                    <StatCard value={newPatientsThisMonth} label={t('ownerDashboard.newPatientsThisMonth')} color={newPatientsThisMonth > 0 ? '#276749' : undefined} />
                    <StatCard value={upcomingCount} label={t('ownerDashboard.upcomingAppointments')} color={upcomingCount > 0 ? '#2b6cb0' : undefined} />
                  </div>
                </div>
                <div>
                  <div style={SEC_LABEL}>{t('ownerDashboard.sectionVisits')}</div>
                  <div className="inventory-stats">
                    <StatCard value={completedThisMonth} label={t('ownerDashboard.completedVisits')} color={completedThisMonth > 0 ? '#276749' : undefined} />
                    <StatCard value={apptThisMonth.filter(a => ['scheduled', 'confirmed', 'checked_in'].includes(a.status)).length} label={t('ownerDashboard.plannedVisits')} color='#2b6cb0' />
                    <StatCard value={cancelledNoShow} label={t('ownerDashboard.cancelledNoShow')} color={cancelledNoShow > 0 ? '#c53030' : undefined} />
                  </div>
                </div>
                <div>
                  <div style={SEC_LABEL}>{t('ownerDashboard.sectionRevenue')}</div>
                  <div className="inventory-stats">
                    <StatCard value={`${fmt(revenueThisMonth)} zł`} label={t('ownerDashboard.revenueThisMonth')} color='#276749' />
                    <StatCard value={outstanding.length} label={t('ownerDashboard.outstandingCount')} color={outstanding.length > 0 ? '#c53030' : '#276749'} />
                    <StatCard value={`${fmt(outstandingAmount)} zł`} label={t('ownerDashboard.outstandingAmount')} color={outstandingAmount > 0 ? '#c53030' : '#276749'} />
                  </div>
                </div>
                <div style={CARD}>
                  <h3 style={CHART_TITLE}>{t('ownerDashboard.topServices')}</h3>
                  {topServices.length === 0
                    ? <p style={{ color: '#718096', fontSize: '0.9rem' }}>{t('ownerDashboard.noData')}</p>
                    : <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
                        {topServices.map(([name, revenue], i) => (
                          <div key={name}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                              <span style={{ fontSize: '0.9rem', color: '#2d3748', fontWeight: i === 0 ? '600' : '400' }}>{i + 1}. {name}</span>
                              <span style={{ fontSize: '0.9rem', fontWeight: '600', color: '#276749' }}>{fmt(revenue)} zł</span>
                            </div>
                            <div style={{ background: '#edf2f7', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${(revenue / maxRevenue) * 100}%`, background: i === 0 ? '#48bb78' : '#9ae6b4', borderRadius: '4px', transition: 'width 0.4s ease' }} />
                            </div>
                          </div>
                        ))}
                      </div>
                  }
                </div>
              </div>
            )}

            {/* ── VISITS ── */}
            {activeTab === 'visits' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <div style={CARD}>
                  <h3 style={CHART_TITLE}>{t('ownerDashboard.visitsByMonth')}</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={visitsByMonth}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey={t('ownerDashboard.completed')} stackId="a" fill={COLORS.completed} radius={[0, 0, 0, 0]} />
                      <Bar dataKey={t('ownerDashboard.cancelled')} stackId="a" fill={COLORS.cancelled} />
                      <Bar dataKey={t('ownerDashboard.noShow')} stackId="a" fill={COLORS.no_show} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                  <div style={CARD}>
                    <h3 style={CHART_TITLE}>{t('ownerDashboard.visitStatusThisMonth')}</h3>
                    {visitStatusPie.length === 0
                      ? <p style={{ color: '#718096', fontSize: '0.9rem' }}>{t('ownerDashboard.noData')}</p>
                      : <ResponsiveContainer width="100%" height={220}>
                          <PieChart>
                            <Pie data={visitStatusPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`} labelLine={false} />
                            <Tooltip />
                          </PieChart>
                        </ResponsiveContainer>
                    }
                  </div>
                  <div style={CARD}>
                    <h3 style={CHART_TITLE}>{t('ownerDashboard.visitsByWeekday')}</h3>
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={visitsByWeekday}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                        <Tooltip />
                        <Bar dataKey={t('ownerDashboard.visits')} fill="#48bb78" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {/* ── REVENUE ── */}
            {activeTab === 'revenue' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <div style={CARD}>
                  <h3 style={CHART_TITLE}>{t('ownerDashboard.revenueByMonth')}</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <AreaChart data={revenueByMonth}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `${v} zł`} />
                      <Tooltip formatter={(v) => `${fmt(v)} zł`} />
                      <Legend />
                      <Area type="monotone" dataKey={t('ownerDashboard.invoiced')} stroke="#63b3ed" fill="#bee3f8" strokeWidth={2} />
                      <Area type="monotone" dataKey={t('ownerDashboard.paid')} stroke="#48bb78" fill="#c6f6d5" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                  <div style={CARD}>
                    <h3 style={CHART_TITLE}>{t('ownerDashboard.invoiceStatusBreakdown')}</h3>
                    {invoiceStatusPie.length === 0
                      ? <p style={{ color: '#718096', fontSize: '0.9rem' }}>{t('ownerDashboard.noData')}</p>
                      : <ResponsiveContainer width="100%" height={220}>
                          <PieChart>
                            <Pie data={invoiceStatusPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`} labelLine={false} />
                            <Tooltip />
                          </PieChart>
                        </ResponsiveContainer>
                    }
                  </div>
                  <div style={CARD}>
                    <h3 style={CHART_TITLE}>{t('ownerDashboard.topServices')}</h3>
                    {topServices.length === 0
                      ? <p style={{ color: '#718096', fontSize: '0.9rem' }}>{t('ownerDashboard.noData')}</p>
                      : <ResponsiveContainer width="100%" height={220}>
                          <BarChart data={topServices.map(([name, v]) => ({ name: name.length > 14 ? name.slice(0, 14) + '…' : name, revenue: v }))} layout="vertical">
                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={v => `${v} zł`} />
                            <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} />
                            <Tooltip formatter={(v) => `${fmt(v)} zł`} />
                            <Bar dataKey="revenue" fill="#48bb78" radius={[0, 4, 4, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                    }
                  </div>
                </div>

                {outstanding.length > 0 && (
                  <div style={CARD}>
                    <h3 style={CHART_TITLE}>{t('ownerDashboard.outstandingInvoices')}</h3>
                    <div className="inventory-table" style={{ marginTop: 0 }}>
                      <table>
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>{t('billing.client')}</th>
                            <th>{t('billing.dueDate')}</th>
                            <th>{t('billing.status.label')}</th>
                            <th style={{ textAlign: 'right' }}>{t('billing.balanceDue')}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {outstanding.sort((a, b) => new Date(a.due_date) - new Date(b.due_date)).map(inv => {
                            const isOverdue = inv.status === 'overdue'
                            const client = inv.client_detail ? `${inv.client_detail.first_name} ${inv.client_detail.last_name}`.trim() : `#${inv.client}`
                            return (
                              <tr key={inv.id}>
                                <td>{inv.invoice_number || inv.id}</td>
                                <td>{client}</td>
                                <td style={{ color: isOverdue ? '#c53030' : undefined }}>
                                  {inv.due_date ? new Date(inv.due_date).toLocaleDateString('pl-PL') : '—'}
                                </td>
                                <td>
                                  <span className="status-badge" style={isOverdue ? { background: '#fff5f5', color: '#c53030' } : { background: '#ebf8ff', color: '#2b6cb0' }}>
                                    {t(`billing.status.${inv.status}`)}
                                  </span>
                                </td>
                                <td style={{ textAlign: 'right', fontWeight: '600', color: '#c53030' }}>
                                  {parseFloat(inv.balance_due).toFixed(2)} {inv.currency}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── PATIENTS ── */}
            {activeTab === 'patients' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <div style={CARD}>
                  <h3 style={CHART_TITLE}>{t('ownerDashboard.newPatientsClientsPerMonth')}</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={patientsByMonth}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey={t('ownerDashboard.newPatients')} fill="#48bb78" radius={[4, 4, 0, 0]} />
                      <Bar dataKey={t('ownerDashboard.newClients')} fill="#63b3ed" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                  <div style={CARD}>
                    <h3 style={CHART_TITLE}>{t('ownerDashboard.speciesBreakdown')}</h3>
                    {speciesPie.length === 0
                      ? <p style={{ color: '#718096', fontSize: '0.9rem' }}>{t('ownerDashboard.noData')}</p>
                      : <ResponsiveContainer width="100%" height={220}>
                          <PieChart>
                            <Pie data={speciesPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`} labelLine={false} />
                            <Tooltip />
                          </PieChart>
                        </ResponsiveContainer>
                    }
                  </div>
                  <div style={CARD}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <StatCard value={clients.length} label={t('ownerDashboard.totalClients')} />
                      <StatCard value={patients.length} label={t('ownerDashboard.totalPatients')} />
                      <StatCard value={newPatientsThisMonth} label={t('ownerDashboard.newPatientsThisMonth')} color={newPatientsThisMonth > 0 ? '#276749' : undefined} />
                      <StatCard value={clients.filter(c => new Date(c.created_at) >= monthStart).length} label={t('ownerDashboard.newClientsThisMonth')} color='#2b6cb0' />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default OwnerDashboardTab
