import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { appointmentsAPI, availabilityAPI } from '../../services/api'
import VisitDetailsModal from '../modals/VisitDetailsModal'
import './Tabs.css'

const CalendarTab = () => {
  const { t, i18n } = useTranslation()
  const [appointments, setAppointments] = useState([])
  const [selectedAppointment, setSelectedAppointment] = useState(null)
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [currentDate, setCurrentDate] = useState(new Date())
  const [availabilityByDay, setAvailabilityByDay] = useState({}) // { 'YYYY-MM-DD': { free: [], busy: [] } }

  const days = [t('calendar.sun'), t('calendar.mon'), t('calendar.tue'), t('calendar.wed'), t('calendar.thu'), t('calendar.fri'), t('calendar.sat')]
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
      
      // Set time boundaries for the week
      weekStart.setHours(0, 0, 0, 0)
      weekEnd.setHours(23, 59, 59, 999)

      // Fetch all appointments (backend doesn't support date range, so we fetch all and filter client-side)
      const response = await appointmentsAPI.list()
      let allAppointments = response.data.results || response.data || []
      
      // Filter appointments to the week range
      allAppointments = allAppointments.filter(apt => {
        const aptDate = new Date(apt.starts_at)
        return aptDate >= weekStart && aptDate < weekEnd
      })
      
      setAppointments(allAppointments)
    } catch (err) {
      console.error('Error fetching appointments:', err)
      setAppointments([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const fetchAvailabilityForWeek = async () => {
      const weekDates = getWeekDates(currentDate)
      const availabilityMap = {}
      
      // Fetch availability for each day in the week (without vet to get clinic-level availability)
      const promises = weekDates.map(async (date) => {
        const dateStr = date.toISOString().split('T')[0] // YYYY-MM-DD format
        try {
          const response = await availabilityAPI.get({ date: dateStr, slot_minutes: 30 })
          availabilityMap[dateStr] = response.data
        } catch (err) {
          console.error(`Error fetching availability for ${dateStr}:`, err)
          availabilityMap[dateStr] = null
        }
      })
      
      await Promise.all(promises)
      setAvailabilityByDay(availabilityMap)
    }

    fetchAppointments()
    fetchAvailabilityForWeek()
  }, [currentDate])

  const weekDates = getWeekDates(currentDate)
  const locale = i18n.language === 'pl' ? 'pl-PL' : 'en-US'
  const monthName = currentDate.toLocaleDateString(locale, { month: 'long', year: 'numeric' })

  const getAppointmentsForCell = (date, hour) => {
    return appointments.filter(apt => {
      const aptStart = new Date(apt.starts_at)
      const aptEnd = apt.ends_at ? new Date(apt.ends_at) : new Date(aptStart.getTime() + 30 * 60 * 1000) // Default 30 min if no end
      
      // Check if appointment is on the same day
      const sameDay = (
        aptStart.getDate() === date.getDate() &&
        aptStart.getMonth() === date.getMonth() &&
        aptStart.getFullYear() === date.getFullYear()
      )
      
      if (!sameDay) return false
      
      // Check if appointment overlaps with this hour slot
      const hourStart = new Date(date)
      hourStart.setHours(hour, 0, 0, 0)
      const hourEnd = new Date(hourStart)
      hourEnd.setHours(hour + 1, 0, 0, 0)
      
      // Appointment overlaps if it starts before hour ends and ends after hour starts
      return aptStart < hourEnd && aptEnd > hourStart
    })
  }

  const navigateWeek = (direction) => {
    const newDate = new Date(currentDate)
    newDate.setDate(newDate.getDate() + (direction * 7))
    setCurrentDate(newDate)
  }

  const formatTime = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit', hour12: false })
  }

  const getCellStatus = (date, hour) => {
    const dateStr = date.toISOString().split('T')[0]
    const availability = availabilityByDay[dateStr]
    
    if (!availability || !availability.workday) {
      return 'unavailable' // Day is closed or no availability data
    }

    const hourStart = new Date(date)
    hourStart.setHours(hour, 0, 0, 0)
    const hourEnd = new Date(hourStart)
    hourEnd.setHours(hour + 1, 0, 0, 0)

    // Check if this hour is within work hours
    const workStart = new Date(availability.workday.start)
    const workEnd = new Date(availability.workday.end)
    
    if (hourEnd <= workStart || hourStart >= workEnd) {
      return 'unavailable' // Outside work hours
    }

    // Check if there's an appointment in this hour
    const cellAppointments = getAppointmentsForCell(date, hour)
    if (cellAppointments.length > 0) {
      return 'busy' // Has appointments
    }

    // Check if this hour overlaps with any free slot
    if (availability.free && availability.free.length > 0) {
      const isFree = availability.free.some((slot) => {
        const slotStart = new Date(slot.start)
        const slotEnd = new Date(slot.end)
        return hourStart < slotEnd && hourEnd > slotStart
      })
      if (isFree) {
        return 'free' // Available time slot
      }
    }

    // If we have work hours but no free slots, it might be busy or unavailable
    if (availability.busy && availability.busy.length > 0) {
      const isBusy = availability.busy.some((busySlot) => {
        const busyStart = new Date(busySlot.start)
        const busyEnd = new Date(busySlot.end)
        return hourStart < busyEnd && hourEnd > busyStart
      })
      if (isBusy) {
        return 'busy'
      }
    }

    // Default to unavailable if we can't determine
    return 'unavailable'
  }

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>{t('calendar.title')}</h2>
        <div className="calendar-controls">
          <button className="btn-secondary" onClick={() => navigateWeek(-1)}>{t('calendar.previous')}</button>
          <span className="calendar-month">{monthName}</span>
          <button className="btn-secondary" onClick={() => navigateWeek(1)}>{t('calendar.next')}</button>
        </div>
      </div>

      <div className="tab-content-wrapper">
        {loading && <div className="loading-message">{t('calendar.loadingCalendar')}</div>}
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
                    const cellStatus = getCellStatus(date, hour)
                    
                    return (
                      <div 
                        key={`${dayIdx}-${hour}`} 
                        className={`calendar-cell calendar-cell-${cellStatus}`}
                        title={cellStatus === 'unavailable' ? t('calendar.notAvailable') : cellStatus === 'busy' ? t('calendar.busy') : t('calendar.available')}
                      >
                        {cellAppointments.map((apt) => {
                          // Format the reason display (remove "Unknown -" prefix if present)
                          let displayReason = apt.reason || t('visits.visit')
                          if (displayReason.startsWith('Unknown - ')) {
                            displayReason = displayReason.replace('Unknown - ', '')
                          }
                          
                          return (
                            <div
                              key={apt.id}
                              className="calendar-event"
                              role="button"
                              tabIndex={0}
                              onClick={(e) => {
                                e.stopPropagation()
                                setSelectedAppointment(apt)
                                setIsDetailsModalOpen(true)
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.preventDefault()
                                  setSelectedAppointment(apt)
                                  setIsDetailsModalOpen(true)
                                }
                              }}
                              style={{ cursor: 'pointer' }}
                            >
                              <span className="event-time">{formatTime(apt.starts_at)}</span>
                              <span className="event-title">{displayReason}</span>
                            </div>
                          )
                        })}
                      </div>
                    )
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <VisitDetailsModal
        isOpen={isDetailsModalOpen}
        onClose={() => {
          setIsDetailsModalOpen(false)
          setSelectedAppointment(null)
        }}
        appointment={selectedAppointment}
      />
    </div>
  )
}

export default CalendarTab
