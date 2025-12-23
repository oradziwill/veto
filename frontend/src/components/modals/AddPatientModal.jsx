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
  const [ownerSearch, setOwnerSearch] = useState('')
  const [ownerSearchResults, setOwnerSearchResults] = useState([])
  const [selectedOwner, setSelectedOwner] = useState(null)
  const [showOwnerDropdown, setShowOwnerDropdown] = useState(false)
  const [loading, setLoading] = useState(false)
  const [searchingClients, setSearchingClients] = useState(false)
  const [error, setError] = useState(null)
  const [showClientModal, setShowClientModal] = useState(false)
  const [showLoginModal, setShowLoginModal] = useState(false)

  useEffect(() => {
    if (isOpen) {
      // Reset form when modal opens
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
      setOwnerSearch('')
      setSelectedOwner(null)
      setOwnerSearchResults([])
      setShowOwnerDropdown(false)
    }
  }, [isOpen])

  // Search for clients when ownerSearch changes
  useEffect(() => {
    const searchClients = async () => {
      if (ownerSearch.trim().length < 2) {
        setOwnerSearchResults([])
        setShowOwnerDropdown(false)
        return
      }

      try {
        setSearchingClients(true)
        const response = await clientsAPI.list({ search: ownerSearch.trim() })
        const results = response.data.results || response.data
        setOwnerSearchResults(results)
        setShowOwnerDropdown(results.length > 0)
      } catch (err) {
        if (err.response?.status === 401) {
          setShowLoginModal(true)
        }
        console.error('Error searching clients:', err)
        setOwnerSearchResults([])
        setShowOwnerDropdown(false)
      } finally {
        setSearchingClients(false)
      }
    }

    const timeoutId = setTimeout(searchClients, 300) // Debounce search
    return () => clearTimeout(timeoutId)
  }, [ownerSearch])

  const handleOwnerSearchChange = (e) => {
    const value = e.target.value
    setOwnerSearch(value)
    if (!value) {
      setSelectedOwner(null)
      setFormData(prev => ({ ...prev, owner: '' }))
      setShowOwnerDropdown(false)
    }
  }

  const handleOwnerSelect = (client) => {
    setSelectedOwner(client)
    setOwnerSearch(`${client.first_name} ${client.last_name}`)
    setFormData(prev => ({ ...prev, owner: client.id }))
    setShowOwnerDropdown(false)
    setOwnerSearchResults([])
  }

  const handleNewClientCreated = (newClient) => {
    setSelectedOwner(newClient)
    setOwnerSearch(`${newClient.first_name} ${newClient.last_name}`)
    setFormData(prev => ({ ...prev, owner: newClient.id }))
    setShowClientModal(false)
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

    // Validate owner is selected
    if (!formData.owner) {
      setError('Please select or create an owner for this patient.')
      setLoading(false)
      return
    }

    try {
      // Prepare data for API - convert owner to integer
      const submitData = {
        ...formData,
        owner: parseInt(formData.owner, 10),
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

          <div className="form-group" style={{ position: 'relative' }}>
            <label htmlFor="owner">Owner *</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                id="owner"
                name="owner"
                value={ownerSearch}
                onChange={handleOwnerSearchChange}
                placeholder="Search for owner by name, phone, or email..."
                style={{ 
                  width: '100%',
                  padding: '0.5rem',
                  fontSize: '1rem',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                }}
                onFocus={() => {
                  if (ownerSearchResults.length > 0) {
                    setShowOwnerDropdown(true)
                  }
                }}
                onBlur={() => {
                  // Delay hiding dropdown to allow clicks on results
                  setTimeout(() => setShowOwnerDropdown(false), 200)
                }}
              />
              {searchingClients && (
                <div style={{ 
                  position: 'absolute', 
                  right: '0.5rem', 
                  top: '50%', 
                  transform: 'translateY(-50%)',
                  fontSize: '0.85rem',
                  color: '#718096'
                }}>
                  Searching...
                </div>
              )}
              {showOwnerDropdown && ownerSearchResults.length > 0 && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  backgroundColor: 'white',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  marginTop: '0.25rem',
                  maxHeight: '200px',
                  overflowY: 'auto',
                  zIndex: 1000,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
                }}>
                  {ownerSearchResults.map(client => (
                    <div
                      key={client.id}
                      onClick={() => handleOwnerSelect(client)}
                      style={{
                        padding: '0.75rem',
                        cursor: 'pointer',
                        borderBottom: '1px solid #eee',
                        transition: 'background-color 0.2s'
                      }}
                      onMouseEnter={(e) => e.target.style.backgroundColor = '#f5f5f5'}
                      onMouseLeave={(e) => e.target.style.backgroundColor = 'white'}
                    >
                      <div style={{ fontWeight: '500' }}>
                        {client.first_name} {client.last_name}
                      </div>
                      {(client.email || client.phone) && (
                        <div style={{ fontSize: '0.85rem', color: '#718096', marginTop: '0.25rem' }}>
                          {client.email && <span>{client.email}</span>}
                          {client.email && client.phone && <span> • </span>}
                          {client.phone && <span>{client.phone}</span>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {ownerSearch.trim().length >= 2 && ownerSearchResults.length === 0 && !searchingClients && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#718096' }}>
                No owners found. Create a new one below.
              </div>
            )}
            <div style={{ marginTop: '0.75rem' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowClientModal(true)}
                style={{ fontSize: '0.9rem', padding: '0.5rem 1rem' }}
              >
                + Create New Owner
              </button>
            </div>
            {selectedOwner && (
              <div style={{ 
                marginTop: '0.5rem', 
                padding: '0.5rem', 
                backgroundColor: '#f0f9ff', 
                borderRadius: '4px',
                fontSize: '0.9rem'
              }}>
                Selected: <strong>{selectedOwner.first_name} {selectedOwner.last_name}</strong>
                {selectedOwner.email && <span> ({selectedOwner.email})</span>}
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
        onSuccess={(newClient) => {
          handleNewClientCreated(newClient)
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
