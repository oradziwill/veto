import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { clientsAPI, patientsAPI, servicesAPI, invoicesAPI } from '../../services/api'
import './Modal.css'

const EMPTY_LINE = { description: '', quantity: 1, unit_price: '', service: '', vat_rate: '8', unit: 'usł' }

const VAT_RATES = ['23', '8', '5', '0', 'zw', 'oo', 'np']

const CreateInvoiceModal = ({ isOpen, onClose, onSuccess }) => {
  const { t } = useTranslation()
  const [clientSearch, setClientSearch] = useState('')
  const [clients, setClients] = useState([])
  const [selectedClient, setSelectedClient] = useState(null)
  const [patients, setPatients] = useState([])
  const [services, setServices] = useState([])
  const [form, setForm] = useState({
    patient: '',
    due_date: '',
    currency: 'PLN',
    status: 'draft',
  })
  const [lines, setLines] = useState([{ ...EMPTY_LINE }])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [clientLoading, setClientLoading] = useState(false)

  // Fetch services once
  useEffect(() => {
    if (!isOpen) return
    servicesAPI.list().then(res => setServices(res.data.results || res.data)).catch(() => {})
  }, [isOpen])

  // Search clients
  useEffect(() => {
    if (!isOpen || clientSearch.length < 2) {
      setClients([])
      return
    }
    setClientLoading(true)
    clientsAPI.list({ search: clientSearch })
      .then(res => setClients(res.data.results || res.data))
      .catch(() => {})
      .finally(() => setClientLoading(false))
  }, [clientSearch, isOpen])

  // Fetch patients when client selected
  useEffect(() => {
    if (!selectedClient) { setPatients([]); return }
    patientsAPI.list({ owner: selectedClient.id })
      .then(res => setPatients(res.data.results || res.data))
      .catch(() => {})
  }, [selectedClient])

  const resetForm = () => {
    setClientSearch('')
    setClients([])
    setSelectedClient(null)
    setPatients([])
    setForm({ patient: '', due_date: '', currency: 'PLN', status: 'draft' })
    setLines([{ ...EMPTY_LINE }])
    setError(null)
  }

  const handleClose = () => { resetForm(); onClose() }

  const handleClientSelect = (client) => {
    setSelectedClient(client)
    setClientSearch(`${client.first_name} ${client.last_name}`)
    setClients([])
    setForm(prev => ({ ...prev, patient: '' }))
  }

  const handleLineChange = (idx, field, value) => {
    setLines(prev => prev.map((line, i) => {
      if (i !== idx) return line
      const updated = { ...line, [field]: value }
      // Auto-fill price from service catalog
      if (field === 'service' && value) {
        const svc = services.find(s => String(s.id) === String(value))
        if (svc) {
          updated.unit_price = svc.price
          updated.description = updated.description || svc.name
        }
      }
      return updated
    }))
  }

  const addLine = () => setLines(prev => [...prev, { ...EMPTY_LINE }])
  const removeLine = (idx) => setLines(prev => prev.filter((_, i) => i !== idx))

  const lineTotal = (line) => {
    const qty = parseFloat(line.quantity) || 0
    const price = parseFloat(line.unit_price) || 0
    return (qty * price).toFixed(2)
  }

  const grandTotal = lines
    .reduce((sum, l) => sum + (parseFloat(lineTotal(l)) || 0), 0)
    .toFixed(2)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!selectedClient) { setError(t('createInvoice.selectClientError')); return }
    const validLines = lines.filter(l => l.description.trim() && l.unit_price !== '')
    if (validLines.length === 0) { setError(t('createInvoice.addLineError')); return }

    setLoading(true)
    setError(null)
    try {
      const payload = {
        client: selectedClient.id,
        patient: form.patient || null,
        due_date: form.due_date || null,
        currency: form.currency,
        status: form.status,
        lines: validLines.map(l => ({
          description: l.description,
          quantity: parseFloat(l.quantity) || 1,
          unit_price: l.unit_price,
          vat_rate: l.vat_rate,
          unit: l.unit,
          ...(l.service ? { service: parseInt(l.service) } : {}),
        })),
      }
      await invoicesAPI.create(payload)
      onSuccess()
      handleClose()
    } catch (err) {
      const data = err.response?.data
      if (data && typeof data === 'object') {
        const msgs = Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
        setError(msgs.join(' | '))
      } else {
        setError(t('createInvoice.createError'))
      }
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content" style={{ maxWidth: '680px', maxHeight: '90vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t('createInvoice.title')}</h2>
          <button className="modal-close" onClick={handleClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          {/* Client */}
          <div className="form-group" style={{ position: 'relative' }}>
            <label>{t('createInvoice.client')} *</label>
            <input
              type="text"
              value={clientSearch}
              onChange={e => { setClientSearch(e.target.value); if (!e.target.value) setSelectedClient(null) }}
              placeholder={t('createInvoice.clientPlaceholder')}
              autoComplete="off"
            />
            {clientLoading && <div style={{ fontSize: '0.8rem', color: '#718096' }}>{t('common.searching')}</div>}
            {clients.length > 0 && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0,
                background: 'white', border: '1px solid #e2e8f0', borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)', zIndex: 10, maxHeight: '200px', overflowY: 'auto'
              }}>
                {clients.map(c => (
                  <div
                    key={c.id}
                    onClick={() => handleClientSelect(c)}
                    style={{ padding: '0.6rem 1rem', cursor: 'pointer', borderBottom: '1px solid #f7fafc' }}
                    onMouseEnter={e => e.currentTarget.style.background = '#f7fafc'}
                    onMouseLeave={e => e.currentTarget.style.background = 'white'}
                  >
                    <strong>{c.first_name} {c.last_name}</strong>
                    {c.phone && <span style={{ color: '#718096', marginLeft: '0.5rem', fontSize: '0.85rem' }}>{c.phone}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Patient + Due date row */}
          <div className="form-row">
            <div className="form-group">
              <label>{t('createInvoice.patient')}</label>
              <select
                value={form.patient}
                onChange={e => setForm(prev => ({ ...prev, patient: e.target.value }))}
                disabled={!selectedClient}
              >
                <option value="">{t('createInvoice.noPatient')}</option>
                {patients.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>{t('createInvoice.dueDate')}</label>
              <input
                type="date"
                value={form.due_date}
                onChange={e => setForm(prev => ({ ...prev, due_date: e.target.value }))}
              />
            </div>
          </div>

          {/* Currency + Status row */}
          <div className="form-row">
            <div className="form-group">
              <label>{t('createInvoice.currency')}</label>
              <select value={form.currency} onChange={e => setForm(prev => ({ ...prev, currency: e.target.value }))}>
                <option value="PLN">PLN</option>
                <option value="EUR">EUR</option>
                <option value="USD">USD</option>
              </select>
            </div>
            <div className="form-group">
              <label>{t('createInvoice.status')}</label>
              <select value={form.status} onChange={e => setForm(prev => ({ ...prev, status: e.target.value }))}>
                <option value="draft">{t('billing.status.draft')}</option>
                <option value="sent">{t('billing.status.sent')}</option>
              </select>
            </div>
          </div>

          {/* Line items */}
          <div style={{ marginTop: '1rem' }}>
            <label style={{ fontWeight: '600', display: 'block', marginBottom: '0.5rem' }}>
              {t('createInvoice.lineItems')}
            </label>

            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ textAlign: 'left', padding: '0.4rem', width: '28%' }}>{t('createInvoice.description')}</th>
                  <th style={{ textAlign: 'left', padding: '0.4rem', width: '20%' }}>{t('createInvoice.service')}</th>
                  <th style={{ textAlign: 'right', padding: '0.4rem', width: '7%' }}>{t('createInvoice.qty')}</th>
                  <th style={{ textAlign: 'left', padding: '0.4rem', width: '8%' }}>{t('createInvoice.unit')}</th>
                  <th style={{ textAlign: 'right', padding: '0.4rem', width: '12%' }}>{t('createInvoice.unitPrice')}</th>
                  <th style={{ textAlign: 'center', padding: '0.4rem', width: '10%' }}>{t('createInvoice.vatRate')}</th>
                  <th style={{ textAlign: 'right', padding: '0.4rem', width: '12%' }}>{t('createInvoice.total')}</th>
                  <th style={{ width: '3%' }}></th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '0.3rem' }}>
                      <input
                        type="text"
                        value={line.description}
                        onChange={e => handleLineChange(idx, 'description', e.target.value)}
                        placeholder={t('createInvoice.descriptionPlaceholder')}
                        style={{ width: '100%', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '0.3rem' }}
                      />
                    </td>
                    <td style={{ padding: '0.3rem' }}>
                      <select
                        value={line.service}
                        onChange={e => handleLineChange(idx, 'service', e.target.value)}
                        style={{ width: '100%', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '0.3rem' }}
                      >
                        <option value="">{t('createInvoice.customLine')}</option>
                        {services.map(s => (
                          <option key={s.id} value={s.id}>{s.name} ({s.price})</option>
                        ))}
                      </select>
                    </td>
                    <td style={{ padding: '0.3rem' }}>
                      <input
                        type="number"
                        value={line.quantity}
                        min="0.01"
                        step="0.01"
                        onChange={e => handleLineChange(idx, 'quantity', e.target.value)}
                        style={{ width: '100%', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '0.3rem', textAlign: 'right' }}
                      />
                    </td>
                    <td style={{ padding: '0.3rem' }}>
                      <input
                        type="text"
                        value={line.unit}
                        onChange={e => handleLineChange(idx, 'unit', e.target.value)}
                        style={{ width: '100%', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '0.3rem' }}
                      />
                    </td>
                    <td style={{ padding: '0.3rem' }}>
                      <input
                        type="number"
                        value={line.unit_price}
                        min="0"
                        step="0.01"
                        onChange={e => handleLineChange(idx, 'unit_price', e.target.value)}
                        placeholder="0.00"
                        style={{ width: '100%', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '0.3rem', textAlign: 'right' }}
                      />
                    </td>
                    <td style={{ padding: '0.3rem' }}>
                      <select
                        value={line.vat_rate}
                        onChange={e => handleLineChange(idx, 'vat_rate', e.target.value)}
                        style={{ width: '100%', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '0.3rem' }}
                      >
                        {VAT_RATES.map(r => (
                          <option key={r} value={r}>{r === 'zw' || r === 'oo' || r === 'np' ? r : `${r}%`}</option>
                        ))}
                      </select>
                    </td>
                    <td style={{ padding: '0.3rem', textAlign: 'right', fontWeight: '500' }}>
                      {lineTotal(line)}
                    </td>
                    <td style={{ padding: '0.3rem', textAlign: 'center' }}>
                      {lines.length > 1 && (
                        <button type="button" onClick={() => removeLine(idx)}
                          style={{ border: 'none', background: 'none', color: '#e53e3e', cursor: 'pointer', fontSize: '1.1rem', lineHeight: 1 }}>
                          ×
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan="4" style={{ textAlign: 'right', padding: '0.5rem', fontWeight: '700' }}>
                    {t('createInvoice.grandTotal')}
                  </td>
                  <td style={{ textAlign: 'right', padding: '0.5rem', fontWeight: '700' }}>
                    {grandTotal} {form.currency}
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            </table>

            <button type="button" onClick={addLine}
              style={{ marginTop: '0.5rem', background: 'none', border: '1px dashed #a0aec0', borderRadius: '6px',
                padding: '0.4rem 1rem', cursor: 'pointer', color: '#4a5568', fontSize: '0.85rem', width: '100%' }}>
              + {t('createInvoice.addLine')}
            </button>
          </div>

          <div className="modal-actions" style={{ marginTop: '1.5rem' }}>
            <button type="button" className="btn-secondary" onClick={handleClose}>
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? t('common.saving') : t('createInvoice.create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default CreateInvoiceModal
