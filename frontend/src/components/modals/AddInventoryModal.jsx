import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { inventoryAPI } from '../../services/api'
import './Modal.css'

const AddInventoryModal = ({ isOpen, onClose, onSuccess }) => {
  const { t } = useTranslation()
  const [formData, setFormData] = useState({
    name: '',
    category: 'other',
    description: '',
    stock_quantity: 0,
    unit: 'units',
    min_stock_level: 0,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: name === 'stock_quantity' || name === 'min_stock_level'
        ? parseInt(value) || 0
        : value
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await inventoryAPI.create(formData)
      onSuccess()
      onClose()
      // Reset form
      setFormData({
        name: '',
        category: 'other',
        description: '',
        stock_quantity: 0,
        unit: 'units',
        min_stock_level: 0,
      })
    } catch (err) {
      setError(err.response?.data?.detail || t('addInventory.createError'))
      console.error('Error creating inventory item:', err)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t('addInventory.title')}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-group">
            <label htmlFor="name">{t('addInventory.itemName')}</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="category">{t('addInventory.category')}</label>
            <select
              id="category"
              name="category"
              value={formData.category}
              onChange={handleChange}
              required
            >
              <option value="medication">{t('inventory.medications')}</option>
              <option value="supplies">{t('inventory.supplies')}</option>
              <option value="equipment">{t('inventory.equipment')}</option>
              <option value="other">{t('inventory.other')}</option>
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="stock_quantity">{t('addInventory.stockQuantity')}</label>
              <input
                type="number"
                id="stock_quantity"
                name="stock_quantity"
                value={formData.stock_quantity}
                onChange={handleChange}
                min="0"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="unit">{t('addInventory.unit')}</label>
              <input
                type="text"
                id="unit"
                name="unit"
                value={formData.unit}
                onChange={handleChange}
                placeholder={t('addInventory.unitPlaceholder')}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="min_stock_level">Minimum Stock Level</label>
            <input
              type="number"
              id="min_stock_level"
              name="min_stock_level"
              value={formData.min_stock_level}
              onChange={handleChange}
              min="0"
            />
          </div>

          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows="3"
            />
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? t('addInventory.creating') : t('addInventory.createItem')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default AddInventoryModal
