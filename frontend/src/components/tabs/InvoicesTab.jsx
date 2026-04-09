import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { fiscalAPI, invoicesAPI } from '../../services/api'
import CreateInvoiceModal from '../modals/CreateInvoiceModal'
import './InvoicesTab.css'

const STATUS_COLORS = {
  draft:     { bg: '#f1f5f9', color: '#475569' },
  sent:      { bg: '#dbeafe', color: '#1e40af' },
  paid:      { bg: '#dcfce7', color: '#15803d' },
  overdue:   { bg: '#fee2e2', color: '#dc2626' },
  cancelled: { bg: '#f3f4f6', color: '#6b7280' },
}

const KSEF_COLORS = {
  accepted: { bg: '#dcfce7', color: '#15803d' },
  pending:  { bg: '#fef9c3', color: '#b45309' },
  error:    { bg: '#fee2e2', color: '#dc2626' },
  rejected: { bg: '#fee2e2', color: '#dc2626' },
}

const InvoicesTab = () => {
  const { t, i18n } = useTranslation()
  const locale = i18n.language === 'pl' ? 'pl-PL' : 'en-US'

  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [ksefSubmitting, setKsefSubmitting] = useState({})
  const [agentCheck, setAgentCheck] = useState({ loading: false, online: null, latencyMs: null, detail: null })

  const fetchInvoices = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (statusFilter) params.status = statusFilter
      const res = await invoicesAPI.list(params)
      setInvoices(res.data.results || res.data || [])
    } catch {
      setError(t('billing.loadError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchInvoices() }, [statusFilter])

  const checkFiscalAgent = async () => {
    setAgentCheck({ loading: true, online: null, latencyMs: null, detail: null })
    try {
      const res = await fiscalAPI.agentStatus()
      setAgentCheck({
        loading: false,
        online: !!res.data?.online,
        latencyMs: res.data?.latency_ms ?? null,
        detail: res.data?.detail ?? null,
      })
    } catch (err) {
      const data = err.response?.data
      setAgentCheck({
        loading: false,
        online: false,
        latencyMs: data?.latency_ms ?? null,
        detail: data?.detail || err.message || 'Error',
      })
    }
  }

  useEffect(() => { checkFiscalAgent() }, [])

  const handleSubmitKsef = async (invoiceId) => {
    setKsefSubmitting(prev => ({ ...prev, [invoiceId]: true }))
    try {
      const res = await invoicesAPI.submitKsef(invoiceId)
      setInvoices(prev => prev.map(inv => inv.id === invoiceId ? res.data : inv))
    } catch (err) {
      alert(err.response?.data?.detail || t('billing.ksefError'))
    } finally {
      setKsefSubmitting(prev => ({ ...prev, [invoiceId]: false }))
    }
  }

  const fmtDate = (d) => d ? new Date(d).toLocaleDateString(locale) : '—'
  const fmtAmount = (a, currency = 'PLN') =>
    `${parseFloat(a || 0).toFixed(2)} ${currency}`

  const paid = invoices.filter(i => i.status === 'paid').length
  const outstanding = invoices.filter(i => ['draft', 'sent', 'overdue'].includes(i.status)).length

  return (
    <div className="inv-root">
      <div className="inv-stats">
        <div className="inv-stat">
          <span className="inv-stat-val">{invoices.length}</span>
          <span className="inv-stat-lbl">{t('billing.totalInvoices')}</span>
        </div>
        <div className="inv-stat">
          <span className="inv-stat-val green">{paid}</span>
          <span className="inv-stat-lbl">{t('billing.paid')}</span>
        </div>
        <div className="inv-stat">
          <span className="inv-stat-val amber">{outstanding}</span>
          <span className="inv-stat-lbl">{t('billing.outstanding')}</span>
        </div>
        <div className="inv-stat inv-agent">
          <span className={`inv-agent-status ${agentCheck.online === true ? 'ok' : agentCheck.online === false ? 'bad' : ''}`}>
            {agentCheck.loading
              ? '…'
              : agentCheck.online === true
                ? 'Online'
                : agentCheck.online === false
                  ? 'Offline'
                  : '—'}
          </span>
          <span className="inv-stat-lbl">Kasa fiskalna (agent)</span>
          <div className="inv-agent-actions">
            <button className="inv-agent-btn" onClick={checkFiscalAgent} disabled={agentCheck.loading}>
              {agentCheck.loading ? 'Testuję…' : 'Test połączenia'}
            </button>
            {(agentCheck.latencyMs !== null || agentCheck.detail) && (
              <div className="inv-agent-meta">
                {agentCheck.latencyMs !== null && <span>{agentCheck.latencyMs}ms</span>}
                {agentCheck.detail && <span className="inv-agent-detail">{agentCheck.detail}</span>}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="inv-toolbar">
        <select
          className="inv-status-filter"
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
        >
          <option value="">{t('billing.allStatuses')}</option>
          <option value="draft">{t('billing.status.draft')}</option>
          <option value="sent">{t('billing.status.sent')}</option>
          <option value="paid">{t('billing.status.paid')}</option>
          <option value="overdue">{t('billing.status.overdue')}</option>
          <option value="cancelled">{t('billing.status.cancelled')}</option>
        </select>
        <button className="inv-new-btn" onClick={() => setIsCreateOpen(true)}>
          {t('createInvoice.newInvoice')}
        </button>
      </div>

      {loading && <div className="inv-loading">{t('billing.loading')}</div>}
      {error && <div className="inv-error">{error}</div>}

      {!loading && !error && invoices.length === 0 && (
        <div className="inv-empty">{t('billing.noInvoices')}</div>
      )}

      {!loading && !error && invoices.length > 0 && (
        <div className="inv-table-wrap">
          <table className="inv-table">
            <thead>
              <tr>
                <th>#</th>
                <th>{t('billing.client')}</th>
                <th>{t('billing.patient')}</th>
                <th>{t('billing.created')}</th>
                <th>{t('billing.dueDate')}</th>
                <th>{t('billing.status.label')}</th>
                <th className="inv-right">{t('billing.total')}</th>
                <th className="inv-right">{t('billing.balanceDue')}</th>
                <th>KSeF</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map(inv => {
                const sc = STATUS_COLORS[inv.status] || STATUS_COLORS.draft
                const kc = KSEF_COLORS[inv.ksef_status] || null
                const clientName = inv.client_detail
                  ? `${inv.client_detail.first_name} ${inv.client_detail.last_name}`
                  : `#${inv.client}`
                const balanceNum = parseFloat(inv.balance_due || 0)
                const canSubmit = !inv.ksef_status || inv.ksef_status === 'error'
                const isSubmitting = ksefSubmitting[inv.id]
                return (
                  <tr key={inv.id}>
                    <td className="inv-num">{inv.invoice_number || `INV-${inv.id}`}</td>
                    <td>{clientName}</td>
                    <td>{inv.patient_detail?.name || '—'}</td>
                    <td>{fmtDate(inv.created_at)}</td>
                    <td>{fmtDate(inv.due_date)}</td>
                    <td>
                      <span className="inv-badge" style={{ background: sc.bg, color: sc.color }}>
                        {t(`billing.status.${inv.status}`)}
                      </span>
                    </td>
                    <td className="inv-right">{fmtAmount(inv.total, inv.currency)}</td>
                    <td className={`inv-right${balanceNum > 0 ? ' inv-balance-due' : ''}`}>
                      {fmtAmount(inv.balance_due, inv.currency)}
                    </td>
                    <td className="inv-ksef-cell">
                      {kc && (
                        <span className="inv-badge" style={{ background: kc.bg, color: kc.color }}>
                          {t(`billing.ksef.${inv.ksef_status}`)}
                        </span>
                      )}
                      {canSubmit && (
                        <button
                          className="inv-ksef-btn"
                          disabled={isSubmitting}
                          onClick={() => handleSubmitKsef(inv.id)}
                        >
                          {isSubmitting ? '…' : t('billing.ksef.submit')}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <CreateInvoiceModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={() => { setIsCreateOpen(false); fetchInvoices() }}
      />
    </div>
  )
}

export default InvoicesTab
