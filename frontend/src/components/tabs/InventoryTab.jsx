import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { inventoryAPI } from '../../services/api'
import AddInventoryModal from '../modals/AddInventoryModal'
import './Tabs.css'

const InventoryTab = () => {
  const { t } = useTranslation()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)

  const fetchInventory = async (search = '', category = '') => {
    try {
      setLoading(true)
      setError(null)
      const params = {}
      if (search) params.search = search
      if (category && category !== 'all') params.category = category
      const response = await inventoryAPI.list(params)
      setItems(response.data.results || response.data)
    } catch (err) {
      setError(t('inventory.loadError'))
      console.error('Error fetching inventory:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchInventory(searchTerm, categoryFilter)
  }, [searchTerm, categoryFilter])

  const stats = {
    total: items.length,
    lowStock: items.filter(item => item.is_low_stock && !item.is_out_of_stock).length,
    outOfStock: items.filter(item => item.is_out_of_stock).length,
  }

  const getStatusBadge = (item) => {
    if (item.is_out_of_stock) {
      return <span className="status-badge out-of-stock">{t('inventory.outOfStock')}</span>
    }
    if (item.is_low_stock) {
      return <span className="status-badge low-stock">{t('inventory.lowStock')}</span>
    }
    return <span className="status-badge in-stock">{t('inventory.inStock')}</span>
  }

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>{t('inventory.title')}</h2>
        <button className="btn-primary" onClick={() => setIsModalOpen(true)}>
          {t('inventory.addItem')}
        </button>
      </div>

      <div className="tab-content-wrapper">
        <div className="inventory-stats">
          <div className="stat-card">
            <div className="stat-value">{stats.total}</div>
            <div className="stat-label">{t('inventory.totalItems')}</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.lowStock}</div>
            <div className="stat-label">{t('inventory.lowStock')}</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.outOfStock}</div>
            <div className="stat-label">{t('inventory.outOfStock')}</div>
          </div>
        </div>

        <div className="search-bar">
          <input
            type="text"
            placeholder={t('inventory.searchPlaceholder')}
            className="search-input"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <select
            className="filter-select"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="all">{t('inventory.allCategories')}</option>
            <option value="medication">{t('inventory.medications')}</option>
            <option value="supplies">{t('inventory.supplies')}</option>
            <option value="equipment">{t('inventory.equipment')}</option>
            <option value="other">{t('inventory.other')}</option>
          </select>
        </div>

        {loading && <div className="loading-message">{t('inventory.loadingInventory')}</div>}
        {error && <div className="error-message">{error}</div>}

        {!loading && !error && (
          <div className="inventory-table">
            <table>
              <thead>
                <tr>
                  <th>{t('inventory.itemName')}</th>
                  <th>{t('inventory.category')}</th>
                  <th>{t('inventory.stock')}</th>
                  <th>{t('inventory.unit')}</th>
                  <th>{t('inventory.status')}</th>
                  <th>{t('inventory.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>
                      {t('inventory.noItemsFound')}
                    </td>
                  </tr>
                ) : (
                  items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.name}</td>
                      <td>{item.category?.charAt(0).toUpperCase() + item.category?.slice(1) || 'Other'}</td>
                      <td>{item.stock_quantity}</td>
                      <td>{item.unit}</td>
                      <td>{getStatusBadge(item)}</td>
                      <td>
                        <button className="btn-link">{t('common.edit')}</button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <AddInventoryModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => {
          fetchInventory(searchTerm, categoryFilter)
        }}
      />
    </div>
  )
}

export default InventoryTab
