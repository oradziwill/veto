import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { appointmentsAPI } from '../../services/api'
import AddAppointmentModal from '../modals/AddAppointmentModal'
import './Tabs.css'

// Placeholder data
const placeholderAppointments = [
  {
    id: 1,
    patient: { name: 'Max', owner: { first_name: 'John', last_name: 'Doe' } },
    reason: 'Routine Checkup',
    starts_at: new Date(new Date().setHours(10, 0, 0, 0)).toISOString(),
    status: 'scheduled',
  },
  {
    id: 2,
    patient: { name: 'Luna', owner: { first_name: 'Jane', last_name: 'Smith' } },
    reason: 'Vaccination',
    starts_at: new Date(new Date().setHours(11, 30, 0, 0)).toISOString(),
    status: 'scheduled',
  },
  {
    id: 3,
    patient: { name: 'Bunny', owner: { first_name: 'Mike', last_name: 'Johnson' } },
    reason: 'Follow-up',
    starts_at: new Date(new Date().setHours(14, 0, 0, 0)).toISOString(),
    status: 'completed',
  },
]

const VisitsTab = () => {
  const { t, i18n } = useTranslation()
  const [appointments, setAppointments] = useState(placeholderAppointments)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('today')
  const [useAPI, setUseAPI] = useState(true)
  const [isModalOpen, setIsModalOpen] = useState(false)

  const getDateRangeParams = (filterType) => {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const toYYYYMMDD = (d) => {
      const y = d.getFullYear()
      const m = String(d.getMonth() + 1).padStart(2, '0')
      const day = String(d.getDate()).padStart(2, '0')
      return `${y}-${m}-${day}`
    }

    switch (filterType) {
      case 'today':
        return { date: toYYYYMMDD(today) }
      case 'week':
        const weekEnd = new Date(today)
        weekEnd.setDate(weekEnd.getDate() + 6)
        return {
          date_from: toYYYYMMDD(today),
          date_to: toYYYYMMDD(weekEnd),
        }
      case 'month':
        const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
        const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0)
        return {
          date_from: toYYYYMMDD(monthStart),
          date_to: toYYYYMMDD(monthEnd),
        }
      default:
        return {}
    }
  }

  const fetchAppointments = async (filterType) => {
    if (!useAPI) {
      setAppointments(placeholderAppointments)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const params = getDateRangeParams(filterType)
      const response = await appointmentsAPI.list(params)
      setAppointments(response.data.results || response.data || [])
    } catch (err) {
      // Fall back to placeholder data on error
      setUseAPI(false)
      setAppointments(placeholderAppointments)
      console.error('Error fetching appointments, using placeholder data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAppointments(filter)
  }, [filter])

  const formatDateTime = (dateString) => {
    const date = new Date(dateString)
    const locale = i18n.language === 'pl' ? 'pl-PL' : 'en-US'
    return {
      time: date.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit' }),
      date: date.toLocaleDateString(locale, { month: 'short', day: 'numeric', year: 'numeric' }),
    }
  }

  const getStatusClass = (status) => {
    const statusMap = {
      scheduled: 'scheduled',
      confirmed: 'scheduled',
      checked_in: 'scheduled',
      completed: 'completed',
      cancelled: 'out-of-stock',
      no_show: 'out-of-stock',
    }
    return statusMap[status] || 'scheduled'
  }

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>{t('visits.title')}</h2>
        <button className="btn-primary" onClick={() => setIsModalOpen(true)}>
          {t('visits.newVisit')}
        </button>
      </div>

      <div className="tab-content-wrapper">
        <div className="visits-filters">
          <button
            className={`filter-btn ${filter === 'today' ? 'active' : ''}`}
            onClick={() => setFilter('today')}
          >
            {t('visits.today')}
          </button>
          <button
            className={`filter-btn ${filter === 'week' ? 'active' : ''}`}
            onClick={() => setFilter('week')}
          >
            {t('visits.thisWeek')}
          </button>
          <button
            className={`filter-btn ${filter === 'month' ? 'active' : ''}`}
            onClick={() => setFilter('month')}
          >
            {t('visits.thisMonth')}
          </button>
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            {t('visits.all')}
          </button>
        </div>

        {loading && <div className="loading-message">{t('visits.loadingVisits')}</div>}

        <div className="visits-list">
          {appointments.length === 0 ? (
            <div className="empty-state">{t('visits.noVisitsFound')}</div>
          ) : (
            appointments.map((appointment) => {
                const { time, date } = formatDateTime(appointment.starts_at)
                return (
                  <div key={appointment.id} className="visit-card">
                    <div className="visit-time">
                      <span className="time">{time}</span>
                      <span className="date">{date}</span>
                    </div>
                    <div className="visit-info">
                      <h3>
                        {(() => {
                          // Remove "Unknown -" prefix from reason if present
                          let displayReason = appointment.reason || t('visits.visit');
                          if (displayReason.startsWith('Unknown - ')) {
                            displayReason = displayReason.replace('Unknown - ', '');
                          }
                          return displayReason;
                        })()}
                      </h3>
                      <p className="visit-owner">
                        {t('visits.owner')} {appointment.patient?.owner
                          ? `${appointment.patient.owner.first_name || ''} ${appointment.patient.owner.last_name || ''}`.trim() || t('common.unknown')
                          : t('common.unknown')}
                      </p>
                      <p className="visit-type">{t('visits.type')} {(() => {
                        let reason = appointment.reason || t('visits.general');
                        // Remove "Unknown -" prefix if present
                        if (reason.startsWith('Unknown - ')) {
                          reason = reason.replace('Unknown - ', '');
                        }
                        // Extract just the reason part if it contains "Pet Name - Reason" format
                        if (reason.includes(' - ')) {
                          const parts = reason.split(' - ');
                          return parts.length > 1 ? parts[1] : parts[0];
                        }
                        return reason;
                      })()}</p>
                    </div>
                    <div className="visit-status">
                      <span className={`status-badge ${getStatusClass(appointment.status)}`}>
                        {appointment.status ? (t(`visits.${appointment.status}`) || appointment.status) : t('visits.scheduled')}
                      </span>
                    </div>
                  </div>
              )
            })
          )}
        </div>
      </div>

      <AddAppointmentModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => {
          fetchAppointments(filter)
          setUseAPI(true)
        }}
      />
    </div>
  )
}

export default VisitsTab
