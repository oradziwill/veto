import React, { useState, useEffect } from 'react'
import {
  appointmentsAPI,
  patientsAPI,
  clientsAPI,
  patientHistoryAPI,
  servicesAPI,
  invoicesAPI,
} from '../../services/api'
import AddClientModal from './AddClientModal'
import './Modal.css'

const StartVisitModal = ({ isOpen, onClose, onSuccess }) => {
  const [ownerSearch, setOwnerSearch] = useState('')
  const [ownerSearchResults, setOwnerSearchResults] = useState([])
  const [selectedOwner, setSelectedOwner] = useState(null)
  const [showOwnerDropdown, setShowOwnerDropdown] = useState(false)
  const [patients, setPatients] = useState([])
  const [loadingPatients, setLoadingPatients] = useState(false)
  const [searchingClients, setSearchingClients] = useState(false)
  const [showClientModal, setShowClientModal] = useState(false)
  
  const [formData, setFormData] = useState({
    patient: '',
    visitNotes: '',
    medication: '',
    medicalReceipts: '',
    additionalNotes: '',
  })
  
  const [services, setServices] = useState([])
  const [selectedServices, setSelectedServices] = useState([]) // { id, name, price } - can add same service multiple times
  const [serviceToAdd, setServiceToAdd] = useState('') // id of service selected in dropdown
  const [loadingServices, setLoadingServices] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [suggestedAppointment, setSuggestedAppointment] = useState(null)

  // Fetch services when modal opens
  useEffect(() => {
    if (!isOpen) return
    const fetchServices = async () => {
      try {
        setLoadingServices(true)
        const response = await servicesAPI.list()
        const data = response.data.results ?? response.data ?? []
        setServices(Array.isArray(data) ? data : [])
      } catch (err) {
        console.error('Error loading services:', err)
        setServices([])
      } finally {
        setLoadingServices(false)
      }
    }
    fetchServices()
    setSelectedServices([])
    setServiceToAdd('')
  }, [isOpen])

  // Check for scheduled appointments at current time when modal opens
  useEffect(() => {
    if (!isOpen) return

    const checkCurrentAppointment = async () => {
      try {
        const now = new Date()
        // Check appointments within the next 30 minutes
        const futureTime = new Date(now.getTime() + 30 * 60 * 1000)
        
        const response = await appointmentsAPI.list()
        const allAppointments = response.data.results || response.data || []
        
        // Find appointments that are scheduled for now (within 30 min window)
        const currentAppointment = allAppointments.find(apt => {
          const aptStart = new Date(apt.starts_at)
          const aptEnd = new Date(apt.ends_at || apt.starts_at)
          // Appointment is "current" if it started within the last 30 min or starts within next 30 min
          return aptStart <= futureTime && aptEnd >= now && apt.status !== 'cancelled'
        })

        if (currentAppointment) {
          setSuggestedAppointment(currentAppointment)
          // Pre-populate owner and patient
          if (currentAppointment.patient) {
            const patient = currentAppointment.patient
            if (patient.owner) {
              setSelectedOwner(patient.owner)
              setOwnerSearch(`${patient.owner.first_name} ${patient.owner.last_name}`)
              setFormData(prev => ({ ...prev, patient: patient.id.toString() }))
              // Load patients for this owner
              loadPatientsForOwner(patient.owner.id)
            }
          }
        } else {
          setSuggestedAppointment(null)
        }
      } catch (err) {
        console.error('Error checking current appointment:', err)
      }
    }

    checkCurrentAppointment()

    // Reset form when modal opens (unless we have a suggested appointment)
    if (!suggestedAppointment) {
      setFormData({
        patient: '',
        visitNotes: '',
        medication: '',
        medicalReceipts: '',
        additionalNotes: '',
      })
      setOwnerSearch('')
      setSelectedOwner(null)
      setOwnerSearchResults([])
      setShowOwnerDropdown(false)
      setPatients([])
      setError(null)
    }
  }, [isOpen])

  const loadPatientsForOwner = async (ownerId) => {
    try {
      setLoadingPatients(true)
      const response = await patientsAPI.list({ owner: ownerId })
      const patientsData = response.data.results || response.data
      setPatients(patientsData)
    } catch (err) {
      console.error('Error loading patients:', err)
      setPatients([])
    } finally {
      setLoadingPatients(false)
    }
  }

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

  // Load patients when owner is selected
  useEffect(() => {
    if (selectedOwner?.id) {
      loadPatientsForOwner(selectedOwner.id)
    } else {
      setPatients([])
      setFormData(prev => ({ ...prev, patient: '' }))
    }
  }, [selectedOwner])

  const handleOwnerSearchChange = (e) => {
    const value = e.target.value
    setOwnerSearch(value)
    if (!value) {
      setSelectedOwner(null)
      setFormData(prev => ({ ...prev, patient: '' }))
      setPatients([])
      setShowOwnerDropdown(false)
    }
  }

  const handleOwnerSelect = (client) => {
    setSelectedOwner(client)
    setOwnerSearch(`${client.first_name} ${client.last_name}`)
    setFormData(prev => ({ ...prev, patient: '' })) // Clear patient when owner changes
    setShowOwnerDropdown(false)
    setOwnerSearchResults([])
  }

  const handleNewClientCreated = (newClient) => {
    setSelectedOwner(newClient)
    setOwnerSearch(`${newClient.first_name} ${newClient.last_name}`)
    setShowClientModal(false)
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
  }

  const addService = () => {
    if (!serviceToAdd) return
    const service = services.find(s => s.id.toString() === serviceToAdd)
    if (service) {
      setSelectedServices(prev => [...prev, { id: service.id, name: service.name, price: service.price }])
      setServiceToAdd('')
    }
  }

  const removeService = (index) => {
    setSelectedServices(prev => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    // Validate patient is selected
    if (!formData.patient) {
      setError('Please select a patient for this visit.')
      setLoading(false)
      return
    }

    // Validate at least one service is added
    if (selectedServices.length === 0) {
      setError('Please add at least one service for this visit.')
      setLoading(false)
      return
    }

    try {
      const patientId = parseInt(formData.patient, 10)
      
      // Combine visit notes, medication, and additional notes into a structured note
      // The API requires 'note' field to be present and non-empty
      const noteParts = []
      if (formData.visitNotes.trim()) {
        noteParts.push(`VISIT NOTES:\n${formData.visitNotes.trim()}`)
      }
      if (formData.medication.trim()) {
        noteParts.push(`MEDICATION:\n${formData.medication.trim()}`)
      }
      if (formData.additionalNotes.trim()) {
        noteParts.push(`ADDITIONAL NOTES:\n${formData.additionalNotes.trim()}`)
      }
      
      const combinedNote = noteParts.join('\n\n')
      
      // Validate that at least one note field is filled (API requires 'note' field)
      if (!combinedNote.trim()) {
        setError('Please enter at least one of: Visit Notes, Medication, or Additional Notes.')
        setLoading(false)
        return
      }

      // Create history entry via patient history endpoint
      // According to PATIENT_VISIT_HISTORY_API.md:
      // - note: required
      // - receipt_summary: optional
      // - appointment: optional (must belong to same patient and clinic)
      const historyData = {
        note: combinedNote.trim(),
        receipt_summary: formData.medicalReceipts.trim() || '',
        ...(suggestedAppointment?.id && { appointment: suggestedAppointment.id }),
      }

      await patientHistoryAPI.create(patientId, historyData)

      // If services are added, create a draft invoice
      if (selectedServices.length > 0 && selectedOwner?.id) {
        const invoiceLines = selectedServices.map(s => ({
          description: s.name,
          quantity: 1,
          unit_price: String(s.price),
          service: s.id,
        }))
        try {
          await invoicesAPI.create({
            client: selectedOwner.id,
            patient: patientId,
            ...(suggestedAppointment?.id && { appointment: suggestedAppointment.id }),
            status: 'draft',
            lines: invoiceLines,
          })
        } catch (invErr) {
          console.error('Error creating invoice:', invErr)
          // Don't fail the whole operation; visit was saved
        }
      }

      // If there's a suggested appointment, update its status to "checked_in" or "completed"
      if (suggestedAppointment) {
        try {
          await appointmentsAPI.update(suggestedAppointment.id, {
            status: 'checked_in',
          })
        } catch (err) {
          console.error('Error updating appointment status:', err)
          // Don't fail the whole operation if status update fails
        }
      }

      onSuccess()
      onClose()
      
      // Reset form
      setFormData({
        patient: '',
        visitNotes: '',
        medication: '',
        medicalReceipts: '',
        additionalNotes: '',
      })
      setSelectedServices([])
      setOwnerSearch('')
      setSelectedOwner(null)
      setSuggestedAppointment(null)
    } catch (err) {
      // Handle API errors according to the API documentation
      let errorMessage = 'Failed to save visit details. Please try again.'
      
      if (err.response?.data) {
        // Handle validation errors from the API
        const errorData = err.response.data
        if (typeof errorData === 'string') {
          errorMessage = errorData
        } else if (errorData.detail) {
          errorMessage = errorData.detail
        } else if (errorData.note) {
          errorMessage = `Note: ${Array.isArray(errorData.note) ? errorData.note.join(', ') : errorData.note}`
        } else if (errorData.appointment) {
          errorMessage = `Appointment: ${Array.isArray(errorData.appointment) ? errorData.appointment.join(', ') : errorData.appointment}`
        } else if (typeof errorData === 'object') {
          // Try to extract first error message
          const firstError = Object.values(errorData)[0]
          errorMessage = Array.isArray(firstError) ? firstError[0] : firstError
        }
      } else if (err.message) {
        errorMessage = err.message
      }
      
      setError(errorMessage)
      console.error('Error saving visit:', err)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
        <div className="modal-header">
          <h2>Start Visit</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          {suggestedAppointment && (
            <div style={{
              padding: '0.75rem',
              backgroundColor: '#e6f3ff',
              borderRadius: '6px',
              marginBottom: '1rem',
              fontSize: '0.9rem'
            }}>
              <strong>Suggested appointment found:</strong> {suggestedAppointment.reason || 'Scheduled visit'}
              <br />
              <span style={{ color: '#666', fontSize: '0.85rem' }}>
                You can modify the patient/owner below if needed.
              </span>
            </div>
          )}

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
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="patient">Patient *</label>
            {loadingPatients ? (
              <div className="loading-text">Loading patients...</div>
            ) : !selectedOwner ? (
              <div style={{ padding: '0.5rem', color: '#718096', fontSize: '0.9rem' }}>
                Please select an owner first
              </div>
            ) : patients.length === 0 ? (
              <div style={{ padding: '0.5rem', color: '#718096', fontSize: '0.9rem' }}>
                No patients found for this owner
              </div>
            ) : (
              <select
                id="patient"
                name="patient"
                value={formData.patient}
                onChange={handleChange}
                required
              >
                <option value="">Select Patient</option>
                {patients.map((patient) => (
                  <option key={patient.id} value={patient.id}>
                    {patient.name} ({patient.species})
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="visitNotes">Visit Notes</label>
            <textarea
              id="visitNotes"
              name="visitNotes"
              value={formData.visitNotes}
              onChange={handleChange}
              rows="4"
              placeholder="Enter visit notes..."
            />
            <small style={{ color: '#666', fontSize: '0.85rem' }}>
              At least one note field (Visit Notes, Medication, or Additional Notes) is required.
            </small>
          </div>

          <div className="form-group">
            <label htmlFor="medication">Medication</label>
            <textarea
              id="medication"
              name="medication"
              value={formData.medication}
              onChange={handleChange}
              rows="3"
              placeholder="Enter prescribed medications..."
            />
          </div>

          <div className="form-group">
            <label htmlFor="medicalReceipts">Medical Receipts</label>
            <input
              type="text"
              id="medicalReceipts"
              name="medicalReceipts"
              value={formData.medicalReceipts}
              onChange={handleChange}
              placeholder="Enter receipt summary (max 255 characters)..."
              maxLength={255}
            />
            <small style={{ color: '#666', fontSize: '0.85rem' }}>
              Optional. Receipt summary information.
            </small>
          </div>

          <div className="form-group">
            <label htmlFor="additionalNotes">Additional Notes</label>
            <textarea
              id="additionalNotes"
              name="additionalNotes"
              value={formData.additionalNotes}
              onChange={handleChange}
              rows="3"
              placeholder="Enter any additional notes..."
            />
          </div>

          <div
            className="form-group"
            style={{
              marginTop: '1.5rem',
              paddingTop: '1.5rem',
              borderTop: '1px solid #e2e8f0',
            }}
          >
            <label>Services *</label>
            <p style={{ fontSize: '0.85rem', color: '#718096', marginBottom: '0.75rem' }}>
              Add services to bill for this visit. A draft invoice will be created.
            </p>
            {loadingServices ? (
              <div className="loading-text">Loading services...</div>
            ) : services.length === 0 ? (
              <div style={{ fontSize: '0.9rem', color: '#718096' }}>
                No services available in the catalog.
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <select
                    value={serviceToAdd}
                    onChange={(e) => setServiceToAdd(e.target.value)}
                    style={{
                      flex: 1,
                      padding: '0.5rem',
                      fontSize: '1rem',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                    }}
                  >
                    <option value="">Choose a service...</option>
                    {services.map((service) => (
                      <option key={service.id} value={service.id}>
                        {service.name} – {service.price} PLN
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={addService}
                    disabled={!serviceToAdd}
                    style={{ padding: '0.5rem 1rem' }}
                  >
                    Add
                  </button>
                </div>
                {selectedServices.length > 0 && (
                  <>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem', marginBottom: '0.75rem' }}>
                      {selectedServices.map((s, index) => (
                        <div
                          key={`${s.id}-${index}`}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '0.5rem 0.75rem',
                            backgroundColor: '#e6fffa',
                            borderRadius: '4px',
                            fontSize: '0.95rem',
                          }}
                        >
                          <span>{s.name} – {s.price} PLN</span>
                          <button
                            type="button"
                            onClick={() => removeService(index)}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#c53030',
                              cursor: 'pointer',
                              padding: '0.25rem',
                              fontSize: '1.1rem',
                              lineHeight: 1,
                            }}
                            title="Remove"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                    <div
                      style={{
                        padding: '0.75rem 1rem',
                        backgroundColor: '#f7fafc',
                        borderRadius: '4px',
                        borderTop: '2px solid #2f855a',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontWeight: '600',
                        fontSize: '1.1rem',
                      }}
                    >
                      <span>Visit balance</span>
                      <span>
                        {selectedServices
                          .reduce((sum, s) => sum + parseFloat(s.price) || 0, 0)
                          .toFixed(2)}{' '}
                        PLN
                      </span>
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading || loadingServices}>
              {loading ? 'Saving...' : 'Save Visit Details'}
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
    </div>
  )
}

export default StartVisitModal

