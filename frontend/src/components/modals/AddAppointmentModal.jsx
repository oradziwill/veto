import React, { useState, useEffect } from 'react'
import { appointmentsAPI, patientsAPI, authAPI, vetsAPI } from '../../services/api'
import './Modal.css'

const formatDateTimeLocal = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

const add30Minutes = (datetimeLocalString) => {
  const date = new Date(datetimeLocalString)
  date.setMinutes(date.getMinutes() + 30)
  return formatDateTimeLocal(date)
}

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
    if (!isOpen) return

    const loadData = async () => {
      try {
        const [patientsRes, vetsRes, userRes] = await Promise.all([
          patientsAPI.list(),
          vetsAPI.list(),
          authAPI.me(),
        ])
        setPatients(patientsRes.data.results || patientsRes.data)
        setVets(vetsRes.data.results || vetsRes.data)
        const user = userRes.data
        setCurrentUser(user)
        if (user.id) {
          setFormData(prev => ({ ...prev, vet: user.id.toString() }))
        }
      } catch (err) {
        console.error('Error loading data:', err)
      }
    }

    loadData()

    const now = new Date()
    const nextHour = new Date(now.getTime() + 60 * 60 * 1000)
    nextHour.setMinutes(0, 0, 0)
    const startTime = formatDateTimeLocal(nextHour)
    setFormData(prev => ({
      ...prev,
      starts_at: startTime,
      ends_at: add30Minutes(startTime),
    }))
  }, [isOpen])

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => {
      const updated = { ...prev, [name]: value }
      if (name === 'starts_at' && value) {
        updated.ends_at = add30Minutes(value)
      }
      return updated
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const appointmentData = {
        ...formData,
        starts_at: new Date(formData.starts_at).toISOString(),
        ends_at: new Date(formData.ends_at).toISOString(),
        patient: parseInt(formData.patient),
        vet: parseInt(formData.vet) || currentUser?.id || null,
      }
      await appointmentsAPI.create(appointmentData)
      onSuccess()
      onClose()
    } catch (err) {
      let errorMessage = 'Failed to create appointment. Please try again.'
      if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail
      } else if (typeof err.response?.data === 'object') {
        const errors = Object.entries(err.response.data)
          .map(([field, messages]) => {
            const fieldLabel = field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
            const msg = Array.isArray(messages) ? messages.join(', ') : String(messages)
            return `${fieldLabel}: ${msg}`
          })
          .join('; ')
        errorMessage = errors || errorMessage
      }
      setError(errorMessage)
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
            <select id="patient" name="patient" value={formData.patient} onChange={handleChange} required>
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
            <select id="vet" name="vet" value={formData.vet} onChange={handleChange} required>
              <option value="">Select Veterinarian</option>
              {vets.map(vet => (
                <option key={vet.id} value={vet.id}>
                  {vet.first_name && vet.last_name ? `${vet.first_name} ${vet.last_name}` : vet.username}
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
                readOnly
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
            <select id="status" name="status" value={formData.status} onChange={handleChange}>
              <option value="scheduled">Scheduled</option>
              <option value="confirmed">Confirmed</option>
              <option value="checked_in">Checked-in</option>
              <option value="completed">Completed</option>
            </select>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
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
