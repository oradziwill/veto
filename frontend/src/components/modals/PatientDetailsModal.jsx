import React, { useState, useEffect, useRef } from 'react'
import { patientHistoryAPI } from '../../services/api'
import './Modal.css'

const PatientDetailsModal = ({ isOpen, onClose, patient }) => {
  const [history, setHistory] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState(null)
  const hasFetchedRef = useRef(false)
  const currentPatientIdRef = useRef(null)

  useEffect(() => {
    // Reset state when modal closes
    if (!isOpen) {
      setHistory([])
      setError(null)
      setLoadingHistory(false)
      hasFetchedRef.current = false
      currentPatientIdRef.current = null
      return
    }

    // Only fetch if we have a patient ID and haven't fetched for this patient yet
    if (patient?.id) {
      // If this is a different patient, reset the fetch flag
      if (currentPatientIdRef.current !== patient.id) {
        hasFetchedRef.current = false
        currentPatientIdRef.current = patient.id
      }

      // Only fetch once per patient ID
      if (!hasFetchedRef.current) {
        hasFetchedRef.current = true
        
        const fetchHistory = async () => {
          try {
            setLoadingHistory(true)
            setError(null)
            const response = await patientHistoryAPI.list(patient.id)
            setHistory(response.data || [])
          } catch (err) {
            console.error('Error fetching patient history:', err)
            setError('Failed to load visit history.')
            setHistory([])
            hasFetchedRef.current = false // Allow retry on error
          } finally {
            setLoadingHistory(false)
          }
        }

        fetchHistory()
      }
    }
  }, [isOpen, patient?.id])

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatDateOnly = (dateString) => {
    if (!dateString) return 'N/A'
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  const calculateAge = (birthDate) => {
    if (!birthDate) return 'Unknown'
    const today = new Date()
    const birth = new Date(birthDate)
    let years = today.getFullYear() - birth.getFullYear()
    let months = today.getMonth() - birth.getMonth()
    if (months < 0) {
      years--
      months += 12
    }
    if (years > 0) {
      return `${years} year${years !== 1 ? 's' : ''}${months > 0 ? `, ${months} month${months !== 1 ? 's' : ''}` : ''}`
    }
    return `${months} month${months !== 1 ? 's' : ''}`
  }

  if (!isOpen || !patient) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '900px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="modal-header">
          <h2>Patient Details</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-form" style={{ padding: '1.5rem' }}>
          {/* Patient Information Section */}
          <div style={{ marginBottom: '2rem' }}>
            <h3 style={{ marginBottom: '1rem', fontSize: '1.25rem', fontWeight: '600', color: '#2d3748' }}>
              Patient Information
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                  Name
                </label>
                <div style={{ fontSize: '1rem', color: '#2d3748', fontWeight: '500' }}>{patient.name || 'N/A'}</div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                  Species
                </label>
                <div style={{ fontSize: '1rem', color: '#2d3748', fontWeight: '500' }}>{patient.species || 'N/A'}</div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                  Breed
                </label>
                <div style={{ fontSize: '1rem', color: '#2d3748', fontWeight: '500' }}>{patient.breed || 'N/A'}</div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                  Sex
                </label>
                <div style={{ fontSize: '1rem', color: '#2d3748', fontWeight: '500' }}>{patient.sex || 'N/A'}</div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                  Birth Date
                </label>
                <div style={{ fontSize: '1rem', color: '#2d3748', fontWeight: '500' }}>
                  {patient.birth_date ? formatDateOnly(patient.birth_date) : 'N/A'}
                </div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                  Age
                </label>
                <div style={{ fontSize: '1rem', color: '#2d3748', fontWeight: '500' }}>{calculateAge(patient.birth_date)}</div>
              </div>
              {patient.microchip_no && (
                <div>
                  <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                    Microchip Number
                  </label>
                  <div style={{ fontSize: '1rem', color: '#2d3748', fontWeight: '500' }}>{patient.microchip_no}</div>
                </div>
              )}
            </div>
            {patient.allergies && (
              <div style={{ marginTop: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                  Allergies
                </label>
                <div style={{ fontSize: '1rem', color: '#2d3748', padding: '0.75rem', backgroundColor: '#fff5f5', borderRadius: '6px', border: '1px solid #fed7d7' }}>
                  {patient.allergies}
                </div>
              </div>
            )}
            {patient.notes && (
              <div style={{ marginTop: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                  Notes
                </label>
                <div style={{ fontSize: '1rem', color: '#2d3748', padding: '0.75rem', backgroundColor: '#f7fafc', borderRadius: '6px', border: '1px solid #e2e8f0', whiteSpace: 'pre-wrap' }}>
                  {patient.notes}
                </div>
              </div>
            )}
          </div>

          {/* Owner Information Section */}
          {patient.owner && (
            <div style={{ marginBottom: '2rem', paddingTop: '1.5rem', borderTop: '2px solid #e2e8f0' }}>
              <h3 style={{ marginBottom: '1rem', fontSize: '1.25rem', fontWeight: '600', color: '#2d3748' }}>
                Owner Information
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                    Name
                  </label>
                  <div style={{ fontSize: '1rem', color: '#2d3748', fontWeight: '500' }}>
                    {patient.owner.first_name} {patient.owner.last_name}
                  </div>
                </div>
                {patient.owner.email && (
                  <div>
                    <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                      Email
                    </label>
                    <div style={{ fontSize: '1rem', color: '#2d3748', fontWeight: '500' }}>{patient.owner.email}</div>
                  </div>
                )}
                {patient.owner.phone && (
                  <div>
                    <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                      Phone
                    </label>
                    <div style={{ fontSize: '1rem', color: '#2d3748', fontWeight: '500' }}>{patient.owner.phone}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Visit History Section */}
          <div style={{ paddingTop: '1.5rem', borderTop: '2px solid #e2e8f0' }}>
            <h3 style={{ marginBottom: '1rem', fontSize: '1.25rem', fontWeight: '600', color: '#2d3748' }}>
              Visit History
            </h3>

            {loadingHistory && (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#718096' }}>Loading visit history...</div>
            )}

            {error && (
              <div style={{ padding: '1rem', backgroundColor: '#fff5f5', borderRadius: '6px', border: '1px solid #fed7d7', color: '#c53030', marginBottom: '1rem' }}>
                {error}
              </div>
            )}

            {!loadingHistory && !error && history.length === 0 && (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#718096', backgroundColor: '#f7fafc', borderRadius: '6px' }}>
                No visit history available for this patient.
              </div>
            )}

            {!loadingHistory && history.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {history.map((entry) => (
                  <div
                    key={entry.id}
                    style={{
                      padding: '1.25rem',
                      backgroundColor: '#f7fafc',
                      borderRadius: '8px',
                      border: '1px solid #e2e8f0',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                      <div>
                        <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#2d3748', marginBottom: '0.25rem' }}>
                          Visit Date: {formatDate(entry.visit_date || entry.created_at)}
                        </div>
                        {entry.created_by_name && (
                          <div style={{ fontSize: '0.8125rem', color: '#718096' }}>
                            Recorded by: {entry.created_by_name}
                          </div>
                        )}
                      </div>
                      {entry.appointment && (
                        <div style={{ fontSize: '0.8125rem', color: '#718096', padding: '0.25rem 0.75rem', backgroundColor: 'white', borderRadius: '4px', border: '1px solid #cbd5e0' }}>
                          Appointment #{entry.appointment}
                        </div>
                      )}
                    </div>
                    {entry.note && (
                      <div style={{ marginBottom: '0.75rem' }}>
                        <div style={{ fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.5rem' }}>
                          Notes:
                        </div>
                        <div
                          style={{
                            fontSize: '0.9375rem',
                            color: '#2d3748',
                            padding: '0.75rem',
                            backgroundColor: 'white',
                            borderRadius: '6px',
                            whiteSpace: 'pre-wrap',
                            lineHeight: '1.6',
                          }}
                        >
                          {entry.note}
                        </div>
                      </div>
                    )}
                    {entry.receipt_summary && (
                      <div>
                        <div style={{ fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }}>
                          Receipt Summary:
                        </div>
                        <div style={{ fontSize: '0.9375rem', color: '#2d3748', fontWeight: '500' }}>
                          {entry.receipt_summary}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="modal-actions" style={{ padding: '1rem 1.5rem', borderTop: '1px solid #e2e8f0' }}>
          <button type="button" className="btn-primary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default PatientDetailsModal

