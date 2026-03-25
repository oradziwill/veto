import React, { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { queueAPI } from '../../services/api'
import AddToQueueModal from '../modals/AddToQueueModal'
import { translateSpecies } from '../../utils/species'
import './Tabs.css'

const REFRESH_INTERVAL_MS = 15000

const WaitingRoomTab = ({ userRole, onCallPatient, hasActiveVisit = false }) => {
  const { t, i18n } = useTranslation()
  const locale = i18n.language === 'pl' ? 'pl-PL' : 'en-US'

  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [actionLoading, setActionLoading] = useState(null) // entry id being actioned

  const fetchQueue = useCallback(async () => {
    try {
      const response = await queueAPI.list()
      setEntries(response.data.results || response.data || [])
    } catch (err) {
      console.error('Error fetching queue:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchQueue()
    const interval = setInterval(fetchQueue, REFRESH_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [fetchQueue])

  const handleMoveUp = async (id) => {
    setActionLoading(id)
    try {
      await queueAPI.moveUp(id)
      await fetchQueue()
    } catch (err) {
      console.error('Error moving up:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleMoveDown = async (id) => {
    setActionLoading(id)
    try {
      await queueAPI.moveDown(id)
      await fetchQueue()
    } catch (err) {
      console.error('Error moving down:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleRemove = async (id) => {
    setActionLoading(id)
    try {
      await queueAPI.remove(id)
      await fetchQueue()
    } catch (err) {
      console.error('Error removing entry:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDismiss = async (id) => {
    setActionLoading(id)
    try {
      await queueAPI.done(id)
      await fetchQueue()
    } catch (err) {
      console.error('Error dismissing entry:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const handleCall = async (id) => {
    setActionLoading(id)
    try {
      const response = await queueAPI.call(id)
      await fetchQueue()
      if (onCallPatient) {
        onCallPatient(response.data)
      }
    } catch (err) {
      console.error('Error calling patient:', err)
    } finally {
      setActionLoading(null)
    }
  }

  const formatTime = (dateString) => {
    if (!dateString) return '—'
    return new Date(dateString).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', hour12: false })
  }

  const canCall = userRole === 'doctor' || userRole === 'admin'

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>{t('waitingRoom.title')}</h2>
        <button className="btn-primary" onClick={() => setIsAddModalOpen(true)}>
          {t('waitingRoom.addPatient')}
        </button>
      </div>

      <div className="tab-content-wrapper">
        {loading && <div className="loading-message">{t('common.loading')}</div>}

        {!loading && entries.length === 0 && (
          <div style={{
            textAlign: 'center',
            padding: '4rem 2rem',
            color: '#718096',
            fontSize: '1rem',
          }}>
            {t('waitingRoom.empty')}
          </div>
        )}

        {entries.map((entry, idx) => {
          const patient = entry.patient
          const ownerName = patient?.owner
            ? `${patient.owner.first_name} ${patient.owner.last_name}`.trim()
            : ''
          const isInProgress = entry.status === 'in_progress'
          const isActioning = actionLoading === entry.id

          return (
            <div
              key={entry.id}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '1rem',
                padding: '1rem 1.25rem',
                marginBottom: '0.75rem',
                background: isInProgress ? '#ebf8ff' : 'white',
                border: `1px solid ${isInProgress ? '#90cdf4' : '#e2e8f0'}`,
                borderLeft: `4px solid ${entry.is_urgent ? '#e53e3e' : isInProgress ? '#4299e1' : '#48bb78'}`,
                borderRadius: '10px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                opacity: isActioning ? 0.6 : 1,
                transition: 'opacity 0.15s',
              }}
            >
              {/* Position number */}
              <div style={{
                minWidth: '2rem',
                height: '2rem',
                borderRadius: '50%',
                background: isInProgress ? '#4299e1' : '#48bb78',
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: '700',
                fontSize: '0.9rem',
                flexShrink: 0,
              }}>
                {idx + 1}
              </div>

              {/* Patient info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {entry.is_urgent && (
                    <span style={{
                      background: '#fed7d7',
                      color: '#c53030',
                      fontSize: '0.75rem',
                      fontWeight: '700',
                      padding: '0.1rem 0.5rem',
                      borderRadius: '999px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                    }}>
                      {t('waitingRoom.urgent')}
                    </span>
                  )}
                  {isInProgress && (
                    <span style={{
                      background: '#bee3f8',
                      color: '#2b6cb0',
                      fontSize: '0.75rem',
                      fontWeight: '700',
                      padding: '0.1rem 0.5rem',
                      borderRadius: '999px',
                    }}>
                      {t('waitingRoom.inProgress')}
                    </span>
                  )}
                  <span style={{ fontWeight: '600', fontSize: '1rem', color: '#2d3748' }}>
                    {patient?.name}
                    {patient?.species && (
                      <span style={{ fontWeight: '400', color: '#718096', marginLeft: '0.35rem' }}>
                        ({translateSpecies(patient.species, t)})
                      </span>
                    )}
                  </span>
                  {ownerName && (
                    <span style={{ color: '#718096', fontSize: '0.9rem' }}>
                      — {ownerName}
                    </span>
                  )}
                </div>

                {entry.chief_complaint && (
                  <div style={{ marginTop: '0.25rem', fontSize: '0.9rem', color: '#4a5568' }}>
                    <span style={{ fontWeight: '500' }}>{t('waitingRoom.complaint')}:</span>{' '}
                    {entry.chief_complaint}
                  </div>
                )}

                <div style={{ marginTop: '0.25rem', fontSize: '0.8rem', color: '#a0aec0' }}>
                  {t('waitingRoom.arrivedAt')}: {formatTime(entry.arrived_at)}
                  {isInProgress && entry.called_by && (
                    <span style={{ marginLeft: '0.75rem' }}>
                      · {entry.called_by.first_name} {entry.called_by.last_name}
                    </span>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0 }}>
                {isInProgress ? (
                  <button
                    onClick={() => handleDismiss(entry.id)}
                    disabled={isActioning}
                    title={t('waitingRoom.dismiss')}
                    style={{
                      padding: '0.3rem 0.6rem',
                      border: '1px solid #e2e8f0',
                      borderRadius: '6px',
                      background: '#f7fafc',
                      color: '#718096',
                      cursor: 'pointer',
                      fontSize: '0.8rem',
                      fontWeight: '500',
                    }}
                  >
                    {t('waitingRoom.dismiss')}
                  </button>
                ) : (
                  <>
                    <button
                      onClick={() => handleMoveUp(entry.id)}
                      disabled={isActioning || idx === 0}
                      title={t('waitingRoom.moveUp')}
                      style={{
                        padding: '0.3rem 0.5rem',
                        border: '1px solid #e2e8f0',
                        borderRadius: '6px',
                        background: 'white',
                        cursor: idx === 0 ? 'default' : 'pointer',
                        opacity: idx === 0 ? 0.3 : 1,
                        fontSize: '0.85rem',
                      }}
                    >
                      ↑
                    </button>
                    <button
                      onClick={() => handleMoveDown(entry.id)}
                      disabled={isActioning || idx === entries.filter(e => e.status === 'waiting').length - 1}
                      title={t('waitingRoom.moveDown')}
                      style={{
                        padding: '0.3rem 0.5rem',
                        border: '1px solid #e2e8f0',
                        borderRadius: '6px',
                        background: 'white',
                        cursor: 'pointer',
                        fontSize: '0.85rem',
                      }}
                    >
                      ↓
                    </button>
                    <button
                      onClick={() => handleRemove(entry.id)}
                      disabled={isActioning}
                      title={t('waitingRoom.patientLeft')}
                      style={{
                        padding: '0.3rem 0.6rem',
                        border: '1px solid #fed7d7',
                        borderRadius: '6px',
                        background: '#fff5f5',
                        color: '#c53030',
                        cursor: 'pointer',
                        fontSize: '0.8rem',
                        fontWeight: '500',
                      }}
                    >
                      {t('waitingRoom.patientLeft')}
                    </button>
                    {canCall && (
                      <button
                        onClick={() => handleCall(entry.id)}
                        disabled={isActioning || hasActiveVisit}
                        title={hasActiveVisit ? t('waitingRoom.closeCurrentFirst') : undefined}
                        style={{
                          padding: '0.4rem 1rem',
                          border: 'none',
                          borderRadius: '6px',
                          background: hasActiveVisit ? '#a0aec0' : '#2f855a',
                          color: 'white',
                          cursor: hasActiveVisit ? 'not-allowed' : 'pointer',
                          fontSize: '0.9rem',
                          fontWeight: '600',
                        }}
                      >
                        {t('waitingRoom.callPatient')}
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <AddToQueueModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={() => {
          setIsAddModalOpen(false)
          fetchQueue()
        }}
      />
    </div>
  )
}

export default WaitingRoomTab
