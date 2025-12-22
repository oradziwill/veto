import React, { useState, useEffect } from 'react'
import { inventoryAPI } from '../../services/api'
import AddInventoryModal from '../modals/AddInventoryModal'
import './Tabs.css'

const InventoryTab = () => {
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
      setError('Failed to load inventory. Please check your connection.')
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
      return <span className="status-badge out-of-stock">Out of Stock</span>
    }
    if (item.is_low_stock) {
      return <span className="status-badge low-stock">Low Stock</span>
    }
    return <span className="status-badge in-stock">In Stock</span>
  }

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>Inventory</h2>
        <button className="btn-primary" onClick={() => setIsModalOpen(true)}>
          + Add Item
        </button>
      </div>

      <div className="tab-content-wrapper">
        <div className="inventory-stats">
          <div className="stat-card">
            <div className="stat-value">{stats.total}</div>
            <div className="stat-label">Total Items</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.lowStock}</div>
            <div className="stat-label">Low Stock</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.outOfStock}</div>
            <div className="stat-label">Out of Stock</div>
          </div>
        </div>

        <div className="search-bar">
          <input
            type="text"
            placeholder="Search inventory items..."
            className="search-input"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <select
            className="filter-select"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="all">All Categories</option>
            <option value="medication">Medications</option>
            <option value="supplies">Supplies</option>
            <option value="equipment">Equipment</option>
            <option value="other">Other</option>
          </select>
        </div>

        {loading && <div className="loading-message">Loading inventory...</div>}
        {error && <div className="error-message">{error}</div>}

        {!loading && !error && (
          <div className="inventory-table">
            <table>
              <thead>
                <tr>
                  <th>Item Name</th>
                  <th>Category</th>
                  <th>Stock</th>
                  <th>Unit</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>
                      No inventory items found
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
                        <button className="btn-link">Edit</button>
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
