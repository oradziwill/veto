import React, { useState, useEffect } from 'react'
import { appointmentsAPI, patientsAPI, authAPI, vetsAPI } from '../../services/api'
import './Modal.css'

const AddAppointmentModal = ({ isOpen, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    patient: '',
    vet: '',
    starts_at: '',
    ends_at: '',
    reason: '',
    status: 'scheduled',
  })
  const [patients, setPatients] = useState([])
  const [vets, setVets] = useState([])
  const [currentUser, setCurrentUser] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (isOpen) {
      fetchPatients()
      fetchVets()
      fetchCurrentUser()
      // Set default times (next hour)
      const now = new Date()
      const nextHour = new Date(now.getTime() + 60 * 60 * 1000)
      nextHour.setMinutes(0)
      const endTime = new Date(nextHour.getTime() + 30 * 60 * 1000)
      
      setFormData(prev => ({
        ...prev,
        starts_at: nextHour.toISOString().slice(0, 16),
        ends_at: endTime.toISOString().slice(0, 16),
      }))
    }
  }, [isOpen])

  const fetchVets = async () => {
    try {
      const response = await vetsAPI.list()
      const vetsData = response.data.results || response.data
      setVets(vetsData)
    } catch (err) {
      console.error('Error fetching vets:', err)
    }
  }

  const fetchCurrentUser = async () => {
    try {
      const response = await authAPI.me()
      setCurrentUser(response.data)
      if (response.data.id) {
        setFormData(prev => ({
          ...prev,
          vet: response.data.id.toString(),
        }))
      }
    } catch (err) {
      console.error('Error fetching current user:', err)
    }
  }

  const fetchPatients = async () => {
    try {
      const response = await patientsAPI.list()
      setPatients(response.data.results || response.data)
    } catch (err) {
      console.error('Error fetching patients:', err)
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
      // Convert datetime-local to ISO format
      const appointmentData = {
        ...formData,
        starts_at: new Date(formData.starts_at).toISOString(),
        ends_at: new Date(formData.ends_at).toISOString(),
        patient: parseInt(formData.patient),
        vet: parseInt(formData.vet) || (currentUser?.id || null),
      }
      await appointmentsAPI.create(appointmentData)
      onSuccess()
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Failed to create appointment. Please try again.')
      console.error('Error creating appointment:', err)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Schedule New Visit</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-group">
            <label htmlFor="patient">Patient *</label>
            <select
              id="patient"
              name="patient"
              value={formData.patient}
              onChange={handleChange}
              required
            >
              <option value="">Select Patient</option>
              {patients.map(patient => (
                <option key={patient.id} value={patient.id}>
                  {patient.name} ({patient.species})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="vet">Veterinarian *</label>
            <select
              id="vet"
              name="vet"
              value={formData.vet}
              onChange={handleChange}
              required
            >
              <option value="">Select Veterinarian</option>
              {vets.map(vet => (
                <option key={vet.id} value={vet.id}>
                  {vet.first_name && vet.last_name 
                    ? `${vet.first_name} ${vet.last_name}` 
                    : vet.username}
                </option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="starts_at">Start Time *</label>
              <input
                type="datetime-local"
                id="starts_at"
                name="starts_at"
                value={formData.starts_at}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="ends_at">End Time *</label>
              <input
                type="datetime-local"
                id="ends_at"
                name="ends_at"
                value={formData.ends_at}
                onChange={handleChange}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="reason">Reason for Visit *</label>
            <input
              type="text"
              id="reason"
              name="reason"
              value={formData.reason}
              onChange={handleChange}
              placeholder="e.g., Routine Checkup, Vaccination"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="status">Status</label>
            <select
              id="status"
              name="status"
              value={formData.status}
              onChange={handleChange}
            >
              <option value="scheduled">Scheduled</option>
              <option value="confirmed">Confirmed</option>
              <option value="checked_in">Checked-in</option>
              <option value="completed">Completed</option>
            </select>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Scheduling...' : 'Schedule Visit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default AddAppointmentModal

