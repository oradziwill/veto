import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { inventoryAPI } from '../../services/api'
import './Modal.css'

const StockMovementModal = ({ isOpen, onClose, onSuccess, item }) => {
  const { t } = useTranslation()
  const [form, setForm] = useState({ kind: 'in', quantity: 1, note: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm(prev => ({ ...prev, [name]: name === 'quantity' ? parseInt(value) || 1 : value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await inventoryAPI.recordMovement({ item: item.id, ...form })
      onSuccess()
      onClose()
      setForm({ kind: 'in', quantity: 1, note: '' })
    } catch (err) {
      const data = err.response?.data
      setError(data?.detail || (data && Object.values(data).flat().join(' ')) || t('stockMovement.error'))
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen || !item) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '420px' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t('stockMovement.title')}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div style={{ padding: '0 1.5rem 0.5rem', color: '#718096', fontSize: '0.9rem' }}>
          <strong style={{ color: '#2d3748' }}>{item.name}</strong>
          {' '}· {t('stockMovement.currentStock')}: <strong>{item.stock_on_hand} {item.unit}</strong>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-group">
            <label>{t('stockMovement.kind')}</label>
            <select name="kind" value={form.kind} onChange={handleChange}>
              <option value="in">{t('stockMovement.in')}</option>
              <option value="out">{t('stockMovement.out')}</option>
              <option value="adjust">{t('stockMovement.adjust')}</option>
            </select>
            <div style={{ fontSize: '0.8rem', color: '#718096', marginTop: '0.25rem' }}>
              {form.kind === 'in' && t('stockMovement.inHint')}
              {form.kind === 'out' && t('stockMovement.outHint')}
              {form.kind === 'adjust' && t('stockMovement.adjustHint')}
            </div>
          </div>

          <div className="form-group">
            <label>{t('stockMovement.quantity')} *</label>
            <input name="quantity" type="number" min="1" value={form.quantity} onChange={handleChange} required />
          </div>

          <div className="form-group">
            <label>{t('stockMovement.note')}</label>
            <input name="note" value={form.note} onChange={handleChange} placeholder={t('stockMovement.notePlaceholder')} />
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? t('common.saving') : t('stockMovement.record')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default StockMovementModal
