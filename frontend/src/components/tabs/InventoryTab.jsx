import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { inventoryAPI } from '../../services/api'
import AddInventoryModal from '../modals/AddInventoryModal'
import StockMovementModal from '../modals/StockMovementModal'
import './Tabs.css'

const InventoryTab = () => {
  const { t } = useTranslation()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [lowStockOnly, setLowStockOnly] = useState(false)
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [editItem, setEditItem] = useState(null)
  const [movementItem, setMovementItem] = useState(null)

  const fetchInventory = async () => {
    try {
      setLoading(true)
      setError(null)
      const params = {}
      if (searchTerm) params.q = searchTerm
      if (categoryFilter && categoryFilter !== 'all') params.category = categoryFilter
      if (lowStockOnly) params.low_stock = '1'
      const res = await inventoryAPI.list(params)
      setItems(res.data.results || res.data)
    } catch {
      setError(t('inventory.loadError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchInventory() }, [searchTerm, categoryFilter, lowStockOnly])

  const stats = {
    total: items.length,
    lowStock: items.filter(i => i.is_low_stock && i.stock_on_hand > 0).length,
    outOfStock: items.filter(i => i.stock_on_hand === 0).length,
  }

  const getStatusBadge = (item) => {
    if (item.stock_on_hand === 0)
      return <span className="status-badge" style={{ background: '#fff5f5', color: '#c53030' }}>{t('inventory.outOfStock')}</span>
    if (item.is_low_stock)
      return <span className="status-badge" style={{ background: '#fffbeb', color: '#b7791f' }}>{t('inventory.lowStock')}</span>
    return <span className="status-badge" style={{ background: '#f0fff4', color: '#276749' }}>{t('inventory.inStock')}</span>
  }

  return (
    <div className="tab-container">
      <div className="tab-header">
        <button className="btn-primary" onClick={() => setIsAddOpen(true)}>
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
            <div className="stat-value" style={{ color: stats.lowStock > 0 ? '#b7791f' : undefined }}>{stats.lowStock}</div>
            <div className="stat-label">{t('inventory.lowStock')}</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: stats.outOfStock > 0 ? '#c53030' : undefined }}>{stats.outOfStock}</div>
            <div className="stat-label">{t('inventory.outOfStock')}</div>
          </div>
        </div>

        <div className="search-bar">
          <input
            type="text"
            placeholder={t('inventory.searchPlaceholder')}
            className="search-input"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
          <select className="filter-select" value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
            <option value="all">{t('inventory.allCategories')}</option>
            <option value="medication">{t('inventory.medication')}</option>
            <option value="supply">{t('inventory.supply')}</option>
            <option value="food">{t('inventory.food')}</option>
            <option value="other">{t('inventory.other')}</option>
          </select>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.9rem', color: '#4a5568', cursor: 'pointer', whiteSpace: 'nowrap' }}>
            <input type="checkbox" checked={lowStockOnly} onChange={e => setLowStockOnly(e.target.checked)} />
            {t('inventory.lowStockOnly')}
          </label>
        </div>

        {loading && <div className="loading-message">{t('inventory.loadingInventory')}</div>}
        {error && <div className="error-message">{error}</div>}

        {!loading && !error && (
          <div className="inventory-table">
            <table>
              <thead>
                <tr>
                  <th>{t('inventory.itemName')}</th>
                  <th>{t('inventory.sku')}</th>
                  <th>{t('inventory.category')}</th>
                  <th style={{ textAlign: 'right' }}>{t('inventory.stock')}</th>
                  <th>{t('inventory.unit')}</th>
                  <th>{t('inventory.status')}</th>
                  <th>{t('inventory.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>
                      {t('inventory.noItemsFound')}
                    </td>
                  </tr>
                ) : (
                  items.map(item => (
                    <tr key={item.id}>
                      <td><strong>{item.name}</strong></td>
                      <td style={{ color: '#718096', fontSize: '0.85rem' }}>{item.sku}</td>
                      <td>{t(`inventory.${item.category}`) || item.category}</td>
                      <td style={{ textAlign: 'right', fontWeight: '600' }}>
                        {item.stock_on_hand}
                        {item.low_stock_threshold > 0 && (
                          <span style={{ color: '#a0aec0', fontWeight: '400', fontSize: '0.8rem' }}>
                            {' '}/ {item.low_stock_threshold}
                          </span>
                        )}
                      </td>
                      <td>{item.unit}</td>
                      <td>{getStatusBadge(item)}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <button className="btn-link" style={{ fontSize: '0.85rem' }}
                          onClick={() => setMovementItem(item)}>
                          {t('inventory.adjust')}
                        </button>
                        {' '}
                        <button className="btn-link" style={{ fontSize: '0.85rem' }}
                          onClick={() => setEditItem(item)}>
                          {t('common.edit')}
                        </button>
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
        isOpen={isAddOpen || !!editItem}
        editItem={editItem}
        onClose={() => { setIsAddOpen(false); setEditItem(null) }}
        onSuccess={() => { fetchInventory(); setIsAddOpen(false); setEditItem(null) }}
      />

      <StockMovementModal
        isOpen={!!movementItem}
        item={movementItem}
        onClose={() => setMovementItem(null)}
        onSuccess={() => { fetchInventory(); setMovementItem(null) }}
      />
    </div>
  )
}

export default InventoryTab
