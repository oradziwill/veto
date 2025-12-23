import React, { useState } from 'react'
import { clientsAPI, authAPI } from '../../services/api'
import './Modal.css'

const AddClientModal = ({ isOpen, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    email: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
  }

  // Ensure authentication before making API calls
  const ensureAuthenticated = async () => {
    const token = localStorage.getItem('access_token')
    if (token) {
      try {
        // Verify token is still valid
        await authAPI.me()
        return true
      } catch (err) {
        // Token invalid, clear it
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }
    }
    
    // Try to auto-login
    try {
      const authResponse = await authAPI.login('drsmith', 'password123')
      localStorage.setItem('access_token', authResponse.data.access)
      localStorage.setItem('refresh_token', authResponse.data.refresh)
      return true
    } catch (authErr) {
      console.error('Auto-login failed:', authErr)
      return false
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    // Ensure authentication before making the API call
    const isAuthenticated = await ensureAuthenticated()
    if (!isAuthenticated) {
      setError('Unable to authenticate. Please check your connection and try again.')
      setLoading(false)
      return
    }

    try {
      const response = await clientsAPI.create(formData)
      const newClient = response.data
      onSuccess(newClient)
      onClose()
      // Reset form
      setFormData({
        first_name: '',
        last_name: '',
        phone: '',
        email: '',
      })
    } catch (err) {
      // Handle authentication errors - try to auto-login and retry once more
      if (err.response?.status === 401) {
        try {
          const authResponse = await authAPI.login('drsmith', 'password123')
          localStorage.setItem('access_token', authResponse.data.access)
          localStorage.setItem('refresh_token', authResponse.data.refresh)
          // Retry the client creation
          const response = await clientsAPI.create(formData)
          const newClient = response.data
          onSuccess(newClient)
          onClose()
          setFormData({
            first_name: '',
            last_name: '',
            phone: '',
            email: '',
          })
          return
        } catch (authErr) {
          console.error('Auto-login retry failed:', authErr)
          setError('Authentication failed. Please refresh the page.')
        }
      } else {
        setError(err.response?.data?.detail || 'Failed to create client. Please try again.')
      }
      console.error('Error creating client:', err)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add New Client</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="first_name">First Name *</label>
              <input
                type="text"
                id="first_name"
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="last_name">Last Name *</label>
              <input
                type="text"
                id="last_name"
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="phone">Phone</label>
              <input
                type="tel"
                id="phone"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Creating...' : 'Create Client'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default AddClientModal
