import React, { useState, useEffect } from 'react'
import { patientsAPI, clientsAPI } from '../../services/api'
import AddClientModal from './AddClientModal'
import LoginModal from '../LoginModal'
import './Modal.css'

const AddPatientModal = ({ isOpen, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    owner: '',
    name: '',
    species: '',
    breed: '',
    sex: '',
    birth_date: '',
    microchip_no: '',
    allergies: '',
    notes: '',
  })
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadingClients, setLoadingClients] = useState(false)
  const [error, setError] = useState(null)
  const [clientsError, setClientsError] = useState(null)
  const [showClientModal, setShowClientModal] = useState(false)
  const [showLoginModal, setShowLoginModal] = useState(false)

  useEffect(() => {
    if (isOpen) {
      fetchClients()
    }
  }, [isOpen])

  const fetchClients = async () => {
    try {
      setLoadingClients(true)
      setClientsError(null)
      // Use in_my_clinic filter to get clients in the current clinic
      const response = await clientsAPI.inMyClinic()
      const clientsData = response.data.results || response.data
      // If no clinic clients, try getting all clients
      if (clientsData.length === 0) {
        const allResponse = await clientsAPI.list()
        const allClients = allResponse.data.results || allResponse.data
        setClients(allClients)
        if (allClients.length === 0) {
          setClientsError('No clients found. Please create a client first.')
        }
      } else {
        setClients(clientsData)
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setClientsError('Authentication required.')
        setShowLoginModal(true)
      } else if (err.code === 'ERR_NETWORK' || err.message?.includes('Network Error')) {
        setClientsError(
          'Cannot connect to server. ' +
          'Make sure Django is running: cd backend && ./venv/bin/python manage.py runserver'
        )
      } else {
        const errorMsg = err.response?.data?.detail || err.message || 'Failed to load clients. Please check your connection.'
        setClientsError(errorMsg)
      }
      console.error('Error fetching clients:', err)
    } finally {
      setLoadingClients(false)
    }
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      // Prepare data for API - convert owner to integer
      const submitData = {
        ...formData,
        owner: formData.owner ? parseInt(formData.owner, 10) : null,
      }
      await patientsAPI.create(submitData)
      onSuccess()
      onClose()
      // Reset form
      setFormData({
        owner: '',
        name: '',
        species: '',
        breed: '',
        sex: '',
        birth_date: '',
        microchip_no: '',
        allergies: '',
        notes: '',
      })
    } catch (err) {
      const errorMessage = err.response?.data?.detail || 
                          (err.response?.data && typeof err.response.data === 'object' 
                            ? JSON.stringify(err.response.data) 
                            : err.response?.data) ||
                          err.message ||
                          'Failed to create patient. Please try again.'
      setError(errorMessage)
      console.error('Error creating patient:', err)
      console.error('Error response:', err.response?.data)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add New Patient</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-group">
            <label htmlFor="owner">Owner *</label>
            {loadingClients ? (
              <div className="loading-text">Loading clients...</div>
            ) : clientsError ? (
              <div className="error-message" style={{ marginBottom: '0.5rem' }}>
                {clientsError}
              </div>
            ) : (
              <select
                id="owner"
                name="owner"
                value={formData.owner}
                onChange={handleChange}
                required
                disabled={clients.length === 0}
              >
                <option value="">
                  {clients.length === 0 ? 'No clients available' : 'Select Owner'}
                </option>
                {clients.map(client => (
                  <option key={client.id} value={client.id}>
                    {client.first_name} {client.last_name}
                    {client.email ? ` (${client.email})` : ''}
                  </option>
                ))}
              </select>
            )}
            {clients.length === 0 && !loadingClients && !clientsError && (
              <div style={{ marginTop: '0.5rem' }}>
                <p className="help-text" style={{ fontSize: '0.85rem', color: '#718096', marginBottom: '0.5rem' }}>
                  No clients found.
                </p>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowClientModal(true)}
                  style={{ fontSize: '0.9rem', padding: '0.5rem 1rem' }}
                >
                  + Create New Client
                </button>
              </div>
            )}
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="name">Patient Name *</label>
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
              <label htmlFor="species">Species *</label>
              <input
                type="text"
                id="species"
                name="species"
                value={formData.species}
                onChange={handleChange}
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="breed">Breed</label>
              <input
                type="text"
                id="breed"
                name="breed"
                value={formData.breed}
                onChange={handleChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="sex">Sex</label>
              <select
                id="sex"
                name="sex"
                value={formData.sex}
                onChange={handleChange}
              >
                <option value="">Select</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Unknown">Unknown</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="birth_date">Birth Date</label>
            <input
              type="date"
              id="birth_date"
              name="birth_date"
              value={formData.birth_date}
              onChange={handleChange}
            />
          </div>

          <div className="form-group">
            <label htmlFor="microchip_no">Microchip Number</label>
            <input
              type="text"
              id="microchip_no"
              name="microchip_no"
              value={formData.microchip_no}
              onChange={handleChange}
            />
          </div>

          <div className="form-group">
            <label htmlFor="allergies">Allergies</label>
            <textarea
              id="allergies"
              name="allergies"
              value={formData.allergies}
              onChange={handleChange}
              rows="2"
            />
          </div>

          <div className="form-group">
            <label htmlFor="notes">Notes</label>
            <textarea
              id="notes"
              name="notes"
              value={formData.notes}
              onChange={handleChange}
              rows="3"
            />
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Creating...' : 'Create Patient'}
            </button>
          </div>
        </form>
      </div>

      <AddClientModal
        isOpen={showClientModal}
        onClose={() => setShowClientModal(false)}
        onSuccess={() => {
          fetchClients()
          setShowClientModal(false)
        }}
      />

      <LoginModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
        onSuccess={() => {
          fetchClients()
          setShowLoginModal(false)
        }}
      />
    </div>
  )
}

export default AddPatientModal
