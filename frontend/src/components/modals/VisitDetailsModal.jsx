import React from 'react'
import { useTranslation } from 'react-i18next'
import './Modal.css'

const VisitDetailsModal = ({ isOpen, onClose, appointment }) => {
  const { t, i18n } = useTranslation()
  const locale = i18n.language === 'pl' ? 'pl-PL' : 'en-US'

  if (!isOpen) return null

  const formatDateTime = (dateString) => {
    if (!dateString) return '—'
    const d = new Date(dateString)
    return d.toLocaleString(locale, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatTimeRange = (start, end) => {
    if (!start) return '—'
    const s = new Date(start)
    const startStr = s.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
    if (!end) return startStr
    const e = new Date(end)
    const endStr = e.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
    return `${startStr} – ${endStr}`
  }

  const getStatusLabel = (status) => {
    if (!status) return '—'
    const key = status === 'no_show' ? 'no_show' : status
    return t(`visits.${key}`) || status
  }

  const owner = appointment?.patient?.owner
  const ownerName = owner
    ? [owner.first_name, owner.last_name].filter(Boolean).join(' ') || t('common.unknown')
    : t('common.unknown')

  let displayReason = appointment?.reason || t('visits.visit')
  if (displayReason.startsWith('Unknown - ')) {
    displayReason = displayReason.replace('Unknown - ', '')
  }

  const vet = appointment?.vet
  const vetName = vet
    ? [vet.first_name, vet.last_name].filter(Boolean).join(' ').trim() || vet.username || `#${vet.id}`
    : appointment?.vet_id ? `#${appointment.vet_id}` : '—'

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
        <div className="modal-header">
          <h2>{t('visitDetails.title')}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div style={{ padding: '1.5rem' }}>
          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.9rem', color: '#718096', marginBottom: '0.25rem' }}>
              {t('visitDetails.dateTime')}
            </div>
            <div style={{ fontWeight: 600, fontSize: '1.1rem' }}>
              {formatDateTime(appointment?.starts_at)}
            </div>
            <div style={{ fontSize: '0.95rem', color: '#4a5568', marginTop: '0.25rem' }}>
              {formatTimeRange(appointment?.starts_at, appointment?.ends_at)}
            </div>
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.9rem', color: '#718096', marginBottom: '0.25rem' }}>
              {t('visitDetails.reason')}
            </div>
            <div style={{ fontWeight: 500 }}>{displayReason}</div>
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.9rem', color: '#718096', marginBottom: '0.25rem' }}>
              {t('visitDetails.patient')}
            </div>
            <div style={{ fontWeight: 500 }}>
              {appointment?.patient?.name || t('common.unknown')}
              {appointment?.patient?.species && (
                <span style={{ color: '#718096', fontWeight: 400 }}> ({appointment.patient.species})</span>
              )}
            </div>
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.9rem', color: '#718096', marginBottom: '0.25rem' }}>
              {t('visitDetails.owner')}
            </div>
            <div>{ownerName}</div>
            {owner?.phone && (
              <div style={{ fontSize: '0.9rem', marginTop: '0.25rem' }}>{owner.phone}</div>
            )}
            {owner?.email && (
              <div style={{ fontSize: '0.9rem' }}>{owner.email}</div>
            )}
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.9rem', color: '#718096', marginBottom: '0.25rem' }}>
              {t('visitDetails.vet')}
            </div>
            <div>{vetName}</div>
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.9rem', color: '#718096', marginBottom: '0.25rem' }}>
              {t('visitDetails.status')}
            </div>
            <span className={`status-badge ${appointment?.status === 'completed' ? 'completed' : 'scheduled'}`}>
              {getStatusLabel(appointment?.status)}
            </span>
          </div>

          {appointment?.internal_notes && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '0.9rem', color: '#718096', marginBottom: '0.25rem' }}>
                {t('visitDetails.internalNotes')}
              </div>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.95rem' }}>{appointment.internal_notes}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default VisitDetailsModal
