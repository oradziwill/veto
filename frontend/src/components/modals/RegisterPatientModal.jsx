import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { clientsAPI, patientsAPI, appointmentsAPI, queueAPI } from '../../services/api'
import './Modal.css'

const toDateStr = (d) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const RegisterPatientModal = ({ isOpen, onClose, onSuccess }) => {
  const { t } = useTranslation()

  const [ownerSearch, setOwnerSearch] = useState('')
  const [ownerSearchResults, setOwnerSearchResults] = useState([])
  const [selectedOwner, setSelectedOwner] = useState(null)
  const [showOwnerDropdown, setShowOwnerDropdown] = useState(false)
  const [searchingClients, setSearchingClients] = useState(false)

  const [patients, setPatients] = useState([])
  const [selectedPatientId, setSelectedPatientId] = useState('')
  const [loadingPatients, setLoadingPatients] = useState(false)

  const [todayAppointments, setTodayAppointments] = useState([])
  const [selectedAppointmentId, setSelectedAppointmentId] = useState('') // '' = auto/none
  const [loadingAppointments, setLoadingAppointments] = useState(false)

  const [chiefComplaint, setChiefComplaint] = useState('')
  const [isUrgent, setIsUrgent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (isOpen) {
      setOwnerSearch('')
      setOwnerSearchResults([])
      setSelectedOwner(null)
      setShowOwnerDropdown(false)
      setPatients([])
      setSelectedPatientId('')
      setTodayAppointments([])
      setSelectedAppointmentId('')
      setChiefComplaint('')
      setIsUrgent(false)
      setError(null)
      setResult(null)
    }
  }, [isOpen])

  useEffect(() => {
    const searchClients = async () => {
      if (ownerSearch.trim().length < 2) {
        setOwnerSearchResults([])
        setShowOwnerDropdown(false)
        return
      }
      if (selectedOwner && ownerSearch.trim() === `${selectedOwner.first_name} ${selectedOwner.last_name}`.trim()) {
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
      } catch {
        setOwnerSearchResults([])
        setShowOwnerDropdown(false)
      } finally {
        setSearchingClients(false)
      }
    }
    const timeout = setTimeout(searchClients, 300)
    return () => clearTimeout(timeout)
  }, [ownerSearch, selectedOwner])

  useEffect(() => {
    if (!selectedOwner) { setPatients([]); setSelectedPatientId(''); return }
    const fetchPatients = async () => {
      setLoadingPatients(true)
      try {
        const response = await patientsAPI.list({ owner: selectedOwner.id })
        const list = response.data.results || response.data || []
        setPatients(list)
        if (list.length === 1) setSelectedPatientId(String(list[0].id))
      } catch {
        setPatients([])
      } finally {
        setLoadingPatients(false)
      }
    }
    fetchPatients()
  }, [selectedOwner])

  useEffect(() => {
    if (!selectedPatientId) { setTodayAppointments([]); setSelectedAppointmentId(''); return }
    const fetchTodayAppointments = async () => {
      setLoadingAppointments(true)
      try {
        const today = toDateStr(new Date())
        const response = await appointmentsAPI.list({ patient: selectedPatientId, date: today })
        const list = (response.data.results || response.data || []).filter(
          a => a.status === 'scheduled' || a.status === 'confirmed'
        )
        setTodayAppointments(list)
        if (list.length === 1) setSelectedAppointmentId(String(list[0].id))
        else setSelectedAppointmentId('')
      } catch {
        setTodayAppointments([])
      } finally {
        setLoadingAppointments(false)
      }
    }
    fetchTodayAppointments()
  }, [selectedPatientId])

  const handleOwnerSearchChange = (e) => {
    const value = e.target.value
    setOwnerSearch(value)
    if (!value) { setSelectedOwner(null); setShowOwnerDropdown(false) }
  }

  const handleOwnerSelect = (client) => {
    setSelectedOwner(client)
    setOwnerSearch(`${client.first_name} ${client.last_name}`)
    setShowOwnerDropdown(false)
    setOwnerSearchResults([])
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!selectedPatientId) { setError(t('addPatient.selectOwnerError')); return }
    setLoading(true)
    try {
      const payload = {
        patient: parseInt(selectedPatientId, 10),
        chief_complaint: chiefComplaint,
        is_urgent: isUrgent,
      }
      if (selectedAppointmentId) payload.appointment_id = parseInt(selectedAppointmentId, 10)
      const response = await queueAPI.registerIncoming(payload)
      setResult(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (dateString) => {
    if (!dateString) return ''
    return new Date(dateString).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', hour12: false })
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
        <div className="modal-header">
          <h2>Zarejestruj pacjenta</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {result ? (
          <div style={{ padding: '1.5rem' }}>
            {result.appointment_matched ? (
              <div style={{ background: '#f0fff4', border: '1px solid #9ae6b4', borderRadius: '10px', padding: '1.25rem', marginBottom: '1rem' }}>
                <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>✅</div>
                <div style={{ fontWeight: '700', color: '#276749', marginBottom: '0.25rem' }}>
                  Znaleziono wizytę i dodano do poczekalni
                </div>
                {result.appointment_detail && (
                  <div style={{ fontSize: '0.9rem', color: '#2f855a' }}>
                    🕐 {formatTime(result.appointment_detail.starts_at)}
                    {result.appointment_detail.reason && ` · ${result.appointment_detail.reason}`}
                    {result.appointment_detail.vet && ` · ${result.appointment_detail.vet.first_name} ${result.appointment_detail.vet.last_name}`}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ background: '#fffaf0', border: '1px solid #fbd38d', borderRadius: '10px', padding: '1.25rem', marginBottom: '1rem' }}>
                <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>📋</div>
                <div style={{ fontWeight: '700', color: '#744210' }}>
                  Brak wizyty — dodano do poczekalni
                </div>
                <div style={{ fontSize: '0.9rem', color: '#975a16', marginTop: '0.25rem' }}>
                  Pacjent będzie widoczny w poczekalni jako wizyta bez terminu.
                </div>
              </div>
            )}
            <button
              className="btn-primary"
              onClick={() => { onSuccess(); onClose() }}
              style={{ width: '100%' }}
            >
              OK
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="modal-form">
            {error && <div className="error-message">{error}</div>}

            {/* Owner search */}
            <div className="form-group" style={{ position: 'relative' }}>
              <label>{t('addPatient.owner')}</label>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={ownerSearch}
                  onChange={handleOwnerSearchChange}
                  placeholder={t('addPatient.ownerSearchPlaceholder')}
                  autoComplete="off"
                  style={{ width: '100%', padding: '0.5rem', fontSize: '1rem', border: '1px solid #ddd', borderRadius: '4px' }}
                  onBlur={() => setTimeout(() => setShowOwnerDropdown(false), 200)}
                  onFocus={() => ownerSearchResults.length > 0 && setShowOwnerDropdown(true)}
                />
                {searchingClients && (
                  <div style={{ position: 'absolute', right: '0.5rem', top: '50%', transform: 'translateY(-50%)', fontSize: '0.85rem', color: '#718096' }}>
                    {t('common.searching')}
                  </div>
                )}
                {showOwnerDropdown && ownerSearchResults.length > 0 && (
                  <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: 'white', border: '1px solid #ddd', borderRadius: '4px', marginTop: '0.25rem', maxHeight: '200px', overflowY: 'auto', zIndex: 1000, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
                    {ownerSearchResults.map(client => (
                      <div
                        key={client.id}
                        onClick={() => handleOwnerSelect(client)}
                        style={{ padding: '0.75rem', cursor: 'pointer', borderBottom: '1px solid #eee' }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'white'}
                      >
                        <div style={{ fontWeight: '500' }}>{client.first_name} {client.last_name}</div>
                        {(client.email || client.phone) && (
                          <div style={{ fontSize: '0.85rem', color: '#718096' }}>
                            {client.email}{client.email && client.phone && ' · '}{client.phone}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Patient select */}
            {selectedOwner && (
              <div className="form-group">
                <label>{t('addAppointment.patient')}</label>
                {loadingPatients ? (
                  <div style={{ color: '#718096', fontSize: '0.9rem' }}>{t('common.loading')}</div>
                ) : (
                  <select value={selectedPatientId} onChange={(e) => setSelectedPatientId(e.target.value)} required>
                    <option value="">{t('addPatient.select')}</option>
                    {patients.map(p => (
                      <option key={p.id} value={p.id}>{p.name} ({p.species})</option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {/* Today's appointments */}
            {selectedPatientId && (
              <div className="form-group">
                <label>Wizyta na dziś</label>
                {loadingAppointments ? (
                  <div style={{ color: '#718096', fontSize: '0.9rem' }}>{t('common.loading')}</div>
                ) : todayAppointments.length === 0 ? (
                  <div style={{ fontSize: '0.9rem', color: '#718096', padding: '0.5rem', background: '#f7fafc', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    Brak zaplanowanej wizyty na dziś
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    {todayAppointments.map(apt => (
                      <label
                        key={apt.id}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '0.6rem',
                          padding: '0.6rem 0.75rem', borderRadius: '8px', cursor: 'pointer',
                          border: `1px solid ${selectedAppointmentId === String(apt.id) ? '#805ad5' : '#e2e8f0'}`,
                          background: selectedAppointmentId === String(apt.id) ? '#faf5ff' : 'white',
                        }}
                      >
                        <input
                          type="radio"
                          name="appointment"
                          value={apt.id}
                          checked={selectedAppointmentId === String(apt.id)}
                          onChange={() => setSelectedAppointmentId(String(apt.id))}
                          style={{ accentColor: '#805ad5' }}
                        />
                        <div>
                          <div style={{ fontWeight: '600', fontSize: '0.9rem', color: '#2d3748' }}>
                            🕐 {formatTime(apt.starts_at)}
                            {apt.reason && ` · ${apt.reason}`}
                          </div>
                          {apt.vet && (
                            <div style={{ fontSize: '0.8rem', color: '#718096' }}>
                              {apt.vet.first_name} {apt.vet.last_name}
                            </div>
                          )}
                        </div>
                      </label>
                    ))}
                    {todayAppointments.length > 1 && (
                      <label
                        style={{
                          display: 'flex', alignItems: 'center', gap: '0.6rem',
                          padding: '0.6rem 0.75rem', borderRadius: '8px', cursor: 'pointer',
                          border: `1px solid ${selectedAppointmentId === '' ? '#718096' : '#e2e8f0'}`,
                          background: selectedAppointmentId === '' ? '#f7fafc' : 'white',
                        }}
                      >
                        <input
                          type="radio"
                          name="appointment"
                          value=""
                          checked={selectedAppointmentId === ''}
                          onChange={() => setSelectedAppointmentId('')}
                        />
                        <div style={{ fontSize: '0.9rem', color: '#718096' }}>Bez powiązania z wizytą</div>
                      </label>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Chief complaint */}
            <div className="form-group">
              <label>Cel wizyty</label>
              <input
                type="text"
                value={chiefComplaint}
                onChange={(e) => setChiefComplaint(e.target.value)}
                placeholder="Krótki opis powodu wizyty..."
              />
            </div>

            {/* Urgent */}
            <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: '0.5rem' }}>
              <input
                type="checkbox"
                id="reg_is_urgent"
                checked={isUrgent}
                onChange={(e) => setIsUrgent(e.target.checked)}
                style={{ width: 'auto', cursor: 'pointer' }}
              />
              <label htmlFor="reg_is_urgent" style={{ marginBottom: 0, cursor: 'pointer', color: isUrgent ? '#c53030' : undefined }}>
                {t('waitingRoom.urgent')}
              </label>
            </div>

            <div className="modal-actions">
              <button type="button" className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
              <button type="submit" className="btn-primary" disabled={loading || !selectedPatientId}>
                {loading ? t('common.saving') : 'Zarejestruj'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

export default RegisterPatientModal
