import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { clientsAPI, patientsAPI, queueAPI } from '../../services/api'
import './Modal.css'

const AddToQueueModal = ({ isOpen, onClose, onSuccess }) => {
  const { t } = useTranslation()

  const [ownerSearch, setOwnerSearch] = useState('')
  const [ownerSearchResults, setOwnerSearchResults] = useState([])
  const [selectedOwner, setSelectedOwner] = useState(null)
  const [showOwnerDropdown, setShowOwnerDropdown] = useState(false)
  const [searchingClients, setSearchingClients] = useState(false)

  const [patients, setPatients] = useState([])
  const [selectedPatientId, setSelectedPatientId] = useState('')
  const [loadingPatients, setLoadingPatients] = useState(false)

  const [chiefComplaint, setChiefComplaint] = useState('')
  const [isUrgent, setIsUrgent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Reset on open
  useEffect(() => {
    if (isOpen) {
      setOwnerSearch('')
      setOwnerSearchResults([])
      setSelectedOwner(null)
      setShowOwnerDropdown(false)
      setPatients([])
      setSelectedPatientId('')
      setChiefComplaint('')
      setIsUrgent(false)
      setError(null)
    }
  }, [isOpen])

  // Owner search debounce
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
        setOwnerSearchResults([])
        setShowOwnerDropdown(false)
      } finally {
        setSearchingClients(false)
      }
    }
    const timeout = setTimeout(searchClients, 300)
    return () => clearTimeout(timeout)
  }, [ownerSearch])

  // Fetch patients when owner selected
  useEffect(() => {
    if (!selectedOwner) {
      setPatients([])
      setSelectedPatientId('')
      return
    }
    const fetchPatients = async () => {
      setLoadingPatients(true)
      try {
        const response = await patientsAPI.list({ owner: selectedOwner.id })
        const list = response.data.results || response.data || []
        setPatients(list)
        if (list.length === 1) setSelectedPatientId(String(list[0].id))
      } catch (err) {
        setPatients([])
      } finally {
        setLoadingPatients(false)
      }
    }
    fetchPatients()
  }, [selectedOwner])

  const handleOwnerSearchChange = (e) => {
    const value = e.target.value
    setOwnerSearch(value)
    if (!value) {
      setSelectedOwner(null)
      setShowOwnerDropdown(false)
    }
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
    if (!selectedPatientId) {
      setError(t('addPatient.selectOwnerError'))
      return
    }
    setLoading(true)
    try {
      await queueAPI.add({
        patient: parseInt(selectedPatientId, 10),
        chief_complaint: chiefComplaint,
        is_urgent: isUrgent,
      })
      onSuccess()
    } catch (err) {
      setError(err.response?.data?.detail || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t('waitingRoom.addPatient')}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          {/* Owner search */}
          <div className="form-group" style={{ position: 'relative' }}>
            <label>{t('addPatient.owner')}</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                name="queue_owner_search_3829471"
                value={ownerSearch}
                onChange={handleOwnerSearchChange}
                placeholder={t('addPatient.ownerSearchPlaceholder')}
                autoComplete="new-password"
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
                      onMouseEnter={(e) => e.target.style.backgroundColor = '#f5f5f5'}
                      onMouseLeave={(e) => e.target.style.backgroundColor = 'white'}
                    >
                      <div style={{ fontWeight: '500' }}>{client.first_name} {client.last_name}</div>
                      {(client.email || client.phone) && (
                        <div style={{ fontSize: '0.85rem', color: '#718096' }}>
                          {client.email}{client.email && client.phone && ' • '}{client.phone}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {selectedOwner && (
              <div style={{ marginTop: '0.5rem', padding: '0.5rem', background: '#f0f9ff', borderRadius: '4px', fontSize: '0.9rem' }}>
                {t('addPatient.selectedLabel')} <strong>{selectedOwner.first_name} {selectedOwner.last_name}</strong>
              </div>
            )}
          </div>

          {/* Patient select */}
          {selectedOwner && (
            <div className="form-group">
              <label>{t('addAppointment.patient')}</label>
              {loadingPatients ? (
                <div style={{ color: '#718096', fontSize: '0.9rem' }}>{t('common.loading')}</div>
              ) : (
                <select
                  value={selectedPatientId}
                  onChange={(e) => setSelectedPatientId(e.target.value)}
                  required
                >
                  <option value="">{t('addPatient.select')}</option>
                  {patients.map(p => (
                    <option key={p.id} value={p.id}>{p.name} ({p.species})</option>
                  ))}
                </select>
              )}
            </div>
          )}

          {/* Chief complaint */}
          <div className="form-group">
            <label>{t('waitingRoom.complaint')}</label>
            <input
              type="text"
              value={chiefComplaint}
              onChange={(e) => setChiefComplaint(e.target.value)}
              placeholder={t('waitingRoom.complaintPlaceholder')}
            />
          </div>

          {/* Urgent checkbox */}
          <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: '0.5rem' }}>
            <input
              type="checkbox"
              id="is_urgent"
              checked={isUrgent}
              onChange={(e) => setIsUrgent(e.target.checked)}
              style={{ width: 'auto', cursor: 'pointer' }}
            />
            <label htmlFor="is_urgent" style={{ marginBottom: 0, cursor: 'pointer', color: isUrgent ? '#c53030' : undefined }}>
              {t('waitingRoom.urgent')}
            </label>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn-primary" disabled={loading || !selectedPatientId}>
              {loading ? t('common.saving') : t('waitingRoom.addToQueue')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default AddToQueueModal
