import React, { useState, useEffect } from 'react'
import { appointmentsAPI } from '../../services/api'
import './Tabs.css'

const CalendarTab = () => {
  const [appointments, setAppointments] = useState([])
  const [loading, setLoading] = useState(true)
  const [currentDate, setCurrentDate] = useState(new Date())

  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  const hours = Array.from({ length: 12 }, (_, i) => i + 8) // 8 AM to 7 PM

  const getWeekStart = (date) => {
    const d = new Date(date)
    const day = d.getDay()
    const diff = d.getDate() - day
    return new Date(d.setDate(diff))
  }

  const getWeekDates = (date) => {
    const weekStart = getWeekStart(date)
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(weekStart)
      d.setDate(d.getDate() + i)
      return d
    })
  }

  const fetchAppointments = async () => {
    try {
      setLoading(true)
      const weekStart = getWeekStart(currentDate)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekEnd.getDate() + 7)

      const params = {
        from: weekStart.toISOString(),
        to: weekEnd.toISOString(),
      }
      const response = await appointmentsAPI.list(params)
      setAppointments(response.data.results || response.data)
    } catch (err) {
      console.error('Error fetching appointments:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAppointments()
  }, [currentDate])

  const weekDates = getWeekDates(currentDate)
  const monthName = currentDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

  const getAppointmentsForCell = (date, hour) => {
    return appointments.filter(apt => {
      const aptDate = new Date(apt.starts_at)
      return (
        aptDate.getDate() === date.getDate() &&
        aptDate.getMonth() === date.getMonth() &&
        aptDate.getFullYear() === date.getFullYear() &&
        aptDate.getHours() === hour
      )
    })
  }

  const navigateWeek = (direction) => {
    const newDate = new Date(currentDate)
    newDate.setDate(newDate.getDate() + (direction * 7))
    setCurrentDate(newDate)
  }

  const formatTime = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: false })
  }

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>Calendar</h2>
        <div className="calendar-controls">
          <button className="btn-secondary" onClick={() => navigateWeek(-1)}>← Previous</button>
          <span className="calendar-month">{monthName}</span>
          <button className="btn-secondary" onClick={() => navigateWeek(1)}>Next →</button>
        </div>
      </div>

      <div className="tab-content-wrapper">
        {loading && <div className="loading-message">Loading calendar...</div>}
        <div className="calendar-view">
          <div className="calendar-grid">
            <div className="calendar-header">
              <div className="time-column"></div>
              {weekDates.map((date, idx) => (
                <div key={idx} className="day-header">
                  <div className="day-name">{days[date.getDay()]}</div>
                  <div className="day-number">{date.getDate()}</div>
                </div>
              ))}
            </div>

            <div className="calendar-body">
              {hours.map((hour) => (
                <div key={hour} className="calendar-row">
                  <div className="time-slot">{hour}:00</div>
                  {weekDates.map((date, dayIdx) => {
                    const cellAppointments = getAppointmentsForCell(date, hour)
                    return (
                      <div key={`${dayIdx}-${hour}`} className="calendar-cell">
                        {cellAppointments.map((apt) => (
                          <div key={apt.id} className="calendar-event">
                            <span className="event-time">{formatTime(apt.starts_at)}</span>
                            <span className="event-title">
                              {apt.patient?.name || 'Unknown'} - {apt.reason || 'Visit'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default CalendarTab
