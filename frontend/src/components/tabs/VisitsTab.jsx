import React, { useState, useEffect } from 'react'
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
  const [appointments, setAppointments] = useState(placeholderAppointments)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('today')
  const [useAPI, setUseAPI] = useState(true)
  const [isModalOpen, setIsModalOpen] = useState(false)

  const getDateRange = (filterType) => {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

    switch (filterType) {
      case 'today':
        return {
          from: today.toISOString(),
          to: new Date(today.getTime() + 24 * 60 * 60 * 1000).toISOString(),
        }
      case 'week':
        const weekStart = today
        const weekEnd = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000)
        return {
          from: weekStart.toISOString(),
          to: weekEnd.toISOString(),
        }
      case 'month':
        const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
        const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 1)
        return {
          from: monthStart.toISOString(),
          to: monthEnd.toISOString(),
        }
      default:
        return {}
    }
  }

  const fetchAppointments = async (filterType) => {
    if (!useAPI) {
      // Use placeholder data
      setAppointments(placeholderAppointments)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const params = getDateRange(filterType)
      const response = await appointmentsAPI.list(params)
      setAppointments(response.data.results || response.data)
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
    return {
      time: date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
      date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
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
        <h2>Visits</h2>
        <button className="btn-primary" onClick={() => setIsModalOpen(true)}>
          + New Visit
        </button>
      </div>

      <div className="tab-content-wrapper">
        <div className="visits-filters">
          <button
            className={`filter-btn ${filter === 'today' ? 'active' : ''}`}
            onClick={() => setFilter('today')}
          >
            Today
          </button>
          <button
            className={`filter-btn ${filter === 'week' ? 'active' : ''}`}
            onClick={() => setFilter('week')}
          >
            This Week
          </button>
          <button
            className={`filter-btn ${filter === 'month' ? 'active' : ''}`}
            onClick={() => setFilter('month')}
          >
            This Month
          </button>
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All
          </button>
        </div>

        {loading && <div className="loading-message">Loading visits...</div>}

        <div className="visits-list">
          {appointments.length === 0 ? (
            <div className="empty-state">No visits found for this period</div>
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
                        {appointment.patient?.name || 'Unknown'} - {appointment.reason || 'Visit'}
                      </h3>
                      <p className="visit-owner">
                        Owner: {appointment.patient?.owner
                          ? `${appointment.patient.owner.first_name} ${appointment.patient.owner.last_name}`
                          : 'Unknown'}
                      </p>
                      <p className="visit-type">Type: {appointment.reason || 'General'}</p>
                    </div>
                    <div className="visit-status">
                      <span className={`status-badge ${getStatusClass(appointment.status)}`}>
                        {appointment.status?.replace('_', ' ').toUpperCase() || 'SCHEDULED'}
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
