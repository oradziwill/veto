import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { inventoryAPI } from '../../services/api'
import './Modal.css'

const EMPTY = { name: '', sku: '', category: 'other', unit: '', stock_on_hand: 0, low_stock_threshold: 0 }

const AddInventoryModal = ({ isOpen, onClose, onSuccess, editItem = null }) => {
  const { t } = useTranslation()
  const [form, setForm] = useState(editItem ? {
    name: editItem.name,
    sku: editItem.sku,
    category: editItem.category,
    unit: editItem.unit,
    stock_on_hand: editItem.stock_on_hand,
    low_stock_threshold: editItem.low_stock_threshold,
  } : EMPTY)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm(prev => ({
      ...prev,
      [name]: name === 'stock_on_hand' || name === 'low_stock_threshold' ? parseInt(value) || 0 : value,
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      if (editItem) {
        await inventoryAPI.update(editItem.id, form)
      } else {
        await inventoryAPI.create(form)
      }
      onSuccess()
      onClose()
      setForm(EMPTY)
    } catch (err) {
      const data = err.response?.data
      if (data && typeof data === 'object') {
        const msgs = Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
        setError(msgs.join(' | '))
      } else {
        setError(t('addInventory.createError'))
      }
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{editItem ? t('addInventory.editTitle') : t('addInventory.title')}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-row">
            <div className="form-group">
              <label>{t('addInventory.itemName')} *</label>
              <input name="name" value={form.name} onChange={handleChange} required />
            </div>
            <div className="form-group">
              <label>{t('addInventory.sku')} *</label>
              <input name="sku" value={form.sku} onChange={handleChange} required placeholder="e.g. AMOX-250" />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>{t('addInventory.category')}</label>
              <select name="category" value={form.category} onChange={handleChange}>
                <option value="medication">{t('inventory.medication')}</option>
                <option value="supply">{t('inventory.supply')}</option>
                <option value="food">{t('inventory.food')}</option>
                <option value="other">{t('inventory.other')}</option>
              </select>
            </div>
            <div className="form-group">
              <label>{t('addInventory.unit')} *</label>
              <input name="unit" value={form.unit} onChange={handleChange} required placeholder={t('addInventory.unitPlaceholder')} />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>{t('addInventory.stockOnHand')}</label>
              <input name="stock_on_hand" type="number" min="0" value={form.stock_on_hand} onChange={handleChange} />
            </div>
            <div className="form-group">
              <label>{t('addInventory.lowStockThreshold')}</label>
              <input name="low_stock_threshold" type="number" min="0" value={form.low_stock_threshold} onChange={handleChange} />
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? t('common.saving') : editItem ? t('common.save') : t('addInventory.createItem')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default AddInventoryModal
