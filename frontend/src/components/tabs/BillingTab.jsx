import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { invoicesAPI } from '../../services/api'
import './Tabs.css'

const STATUS_COLORS = {
  draft:     { background: '#edf2f7', color: '#4a5568' },
  sent:      { background: '#ebf8ff', color: '#2b6cb0' },
  paid:      { background: '#f0fff4', color: '#276749' },
  overdue:   { background: '#fff5f5', color: '#c53030' },
  cancelled: { background: '#fafafa', color: '#718096' },
}

const BillingTab = () => {
  const { t } = useTranslation()
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')

  const fetchInvoices = async (status = '') => {
    try {
      setLoading(true)
      setError(null)
      const params = {}
      if (status && status !== 'all') params.status = status
      const response = await invoicesAPI.list(params)
      setInvoices(response.data.results || response.data)
    } catch (err) {
      setError(t('billing.loadError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchInvoices(statusFilter)
  }, [statusFilter])

  const stats = {
    total: invoices.length,
    paid: invoices.filter(i => i.status === 'paid').length,
    outstanding: invoices
      .filter(i => ['draft', 'sent', 'overdue'].includes(i.status))
      .reduce((sum, i) => sum + parseFloat(i.balance_due || 0), 0)
      .toFixed(2),
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return '—'
    return new Date(dateStr).toLocaleDateString()
  }

  const clientName = (invoice) => {
    if (invoice.client_detail) {
      const { first_name, last_name } = invoice.client_detail
      return `${first_name} ${last_name}`.trim()
    }
    return `#${invoice.client}`
  }

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>{t('billing.title')}</h2>
      </div>

      <div className="tab-content-wrapper">
        <div className="inventory-stats">
          <div className="stat-card">
            <div className="stat-value">{stats.total}</div>
            <div className="stat-label">{t('billing.totalInvoices')}</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.paid}</div>
            <div className="stat-label">{t('billing.paid')}</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.outstanding} zł</div>
            <div className="stat-label">{t('billing.outstanding')}</div>
          </div>
        </div>

        <div className="search-bar">
          <select
            className="filter-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">{t('billing.allStatuses')}</option>
            <option value="draft">{t('billing.status.draft')}</option>
            <option value="sent">{t('billing.status.sent')}</option>
            <option value="paid">{t('billing.status.paid')}</option>
            <option value="overdue">{t('billing.status.overdue')}</option>
            <option value="cancelled">{t('billing.status.cancelled')}</option>
          </select>
        </div>

        {loading && <div className="loading-message">{t('billing.loading')}</div>}
        {error && <div className="error-message">{error}</div>}

        {!loading && !error && (
          <div className="inventory-table">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t('billing.client')}</th>
                  <th>{t('billing.patient')}</th>
                  <th>{t('billing.status.label')}</th>
                  <th>{t('billing.dueDate')}</th>
                  <th>{t('billing.total')}</th>
                  <th>{t('billing.balanceDue')}</th>
                  <th>{t('billing.created')}</th>
                </tr>
              </thead>
              <tbody>
                {invoices.length === 0 ? (
                  <tr>
                    <td colSpan="8" style={{ textAlign: 'center', padding: '2rem' }}>
                      {t('billing.noInvoices')}
                    </td>
                  </tr>
                ) : (
                  invoices.map((invoice) => {
                    const colors = STATUS_COLORS[invoice.status] || STATUS_COLORS.draft
                    return (
                      <tr key={invoice.id}>
                        <td>{invoice.id}</td>
                        <td>{clientName(invoice)}</td>
                        <td>{invoice.patient_detail?.name || '—'}</td>
                        <td>
                          <span className="status-badge" style={colors}>
                            {t(`billing.status.${invoice.status}`)}
                          </span>
                        </td>
                        <td>{formatDate(invoice.due_date)}</td>
                        <td>{invoice.total} {invoice.currency}</td>
                        <td>{invoice.balance_due} {invoice.currency}</td>
                        <td>{formatDate(invoice.created_at)}</td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default BillingTab
