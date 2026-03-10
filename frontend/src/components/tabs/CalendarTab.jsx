import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { appointmentsAPI, availabilityAPI, roomsAPI, schedulerAPI } from '../../services/api'
import VisitDetailsModal from '../modals/VisitDetailsModal'
import AddAppointmentModal from '../modals/AddAppointmentModal'
import './Tabs.css'

const CalendarTab = ({ vets = null, vetId = null, onVetChange = null, onStartVisit = null, currentUserId = null }) => {
  const { t, i18n } = useTranslation()
  const [appointments, setAppointments] = useState([])
  const [rooms, setRooms] = useState([])
  const [viewMode, setViewMode] = useState('week') // 'week' | 'room'
  const [selectedAppointment, setSelectedAppointment] = useState(null)
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false)
  const [isStartVisitModalOpen, setIsStartVisitModalOpen] = useState(false)
  const [clickedSlotTime, setClickedSlotTime] = useState(null)
  const [loading, setLoading] = useState(true)
  const [currentDate, setCurrentDate] = useState(new Date())
  const [availabilityByDay, setAvailabilityByDay] = useState({}) // { 'YYYY-MM-DD': { free: [], busy: [] } }
  const [availabilityByRoomByDay, setAvailabilityByRoomByDay] = useState({}) // { 'YYYY-MM-DD': { rooms: [...] } }
  const [dutyAssignments, setDutyAssignments] = useState([]) // DutyAssignment records for current user

  const days = [t('calendar.sun'), t('calendar.mon'), t('calendar.tue'), t('calendar.wed'), t('calendar.thu'), t('calendar.fri'), t('calendar.sat')]
  const hours = Array.from({ length: 12 }, (_, i) => i + 8) // 8 AM to 7 PM

  const formatDateTimeLocal = (date) => {
    const y = date.getFullYear()
    const m = String(date.getMonth() + 1).padStart(2, '0')
    const d = String(date.getDate()).padStart(2, '0')
    const h = String(date.getHours()).padStart(2, '0')
    const min = String(date.getMinutes()).padStart(2, '0')
    return `${y}-${m}-${d}T${h}:${min}`
  }

  const handleCellClick = (date, hour) => {
    const slotDate = new Date(date)
    slotDate.setHours(hour, 0, 0, 0)
    setClickedSlotTime(formatDateTimeLocal(slotDate))
    setIsStartVisitModalOpen(true)
  }

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
      const params = vetId ? { vet: vetId } : {}
      const response = await appointmentsAPI.list(params)
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
      
      const promises = weekDates.map(async (date) => {
        const dateStr = date.toISOString().split('T')[0]
        try {
          const availParams = { date: dateStr, slot_minutes: 30 }
          if (vetId) availParams.vet = vetId
          const response = await availabilityAPI.get(availParams)
          availabilityMap[dateStr] = response.data
        } catch (err) {
          console.error(`Error fetching availability for ${dateStr}:`, err)
          availabilityMap[dateStr] = null
        }
      })
      
      await Promise.all(promises)
      setAvailabilityByDay(availabilityMap)
    }

    const fetchRoomsAndRoomAvailability = async () => {
      try {
        const roomsRes = await roomsAPI.list()
        setRooms(roomsRes.data.results || roomsRes.data || [])
      } catch (err) {
        console.error('Error fetching rooms:', err)
        setRooms([])
      }
      const weekDates = getWeekDates(currentDate)
      const roomAvailabilityMap = {}
      await Promise.all(weekDates.map(async (date) => {
        const dateStr = date.toISOString().split('T')[0]
        try {
          const response = await availabilityAPI.rooms({ date: dateStr })
          roomAvailabilityMap[dateStr] = response.data
        } catch (err) {
          console.error(`Error fetching room availability for ${dateStr}:`, err)
          roomAvailabilityMap[dateStr] = { rooms: [] }
        }
      }))
      setAvailabilityByRoomByDay(roomAvailabilityMap)
    }

    const fetchDutyAssignments = async () => {
      const dutyVetId = vetId || currentUserId
      if (!dutyVetId) return
      const weekStart = getWeekStart(currentDate)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekEnd.getDate() + 6)
      const from = weekStart.toISOString().split('T')[0]
      const to = weekEnd.toISOString().split('T')[0]
      try {
        const res = await schedulerAPI.listAssignments({ from, to, vet: dutyVetId })
        setDutyAssignments(res.data.results || res.data || [])
      } catch (err) {
        console.error('Error fetching duty assignments:', err)
        setDutyAssignments([])
      }
    }

    fetchAppointments()
    fetchAvailabilityForWeek()
    fetchRoomsAndRoomAvailability()
    fetchDutyAssignments()
  }, [currentDate, vetId, currentUserId])

  const weekDates = getWeekDates(currentDate)
  const locale = i18n.language === 'pl' ? 'pl-PL' : 'en-US'
  const monthName = currentDate.toLocaleDateString(locale, { month: 'long', year: 'numeric' })

  const getAppointmentsForRoomAndDay = (roomId, date) => {
    return appointments.filter((apt) => {
      const aptDate = new Date(apt.starts_at)
      const sameDay =
        aptDate.getDate() === date.getDate() &&
        aptDate.getMonth() === date.getMonth() &&
        aptDate.getFullYear() === date.getFullYear()
      if (!sameDay) return false
      const aptRoomId = apt.room?.id ?? null
      return aptRoomId === roomId
    })
  }

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

  const getDutyForCell = (date, hour) => {
    const dateStr = date.toISOString().split('T')[0]
    return dutyAssignments.filter(duty => {
      if (duty.date !== dateStr) return false
      const [startH, startM] = duty.start_time.split(':').map(Number)
      const [endH, endM] = duty.end_time.split(':').map(Number)
      const dutyStartMins = startH * 60 + startM
      const dutyEndMins = endH * 60 + endM
      const cellStartMins = hour * 60
      const cellEndMins = (hour + 1) * 60
      return dutyStartMins < cellEndMins && dutyEndMins > cellStartMins
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
        <button className="btn-primary" onClick={() => setIsStartVisitModalOpen(true)}>
          {t('visits.newVisit')}
        </button>
      </div>

      <div className="calendar-controls" style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.75rem', flexWrap: 'wrap', padding: '0 0 1rem 0' }}>
        {vets && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginRight: 'auto' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: '500', color: '#4a5568' }}>{t('calendar.doctor')}</label>
            <select
              value={vetId || ''}
              onChange={e => onVetChange(e.target.value ? Number(e.target.value) : null)}
              style={{ padding: '0.35rem 0.6rem', fontSize: '0.875rem', border: '1px solid #e2e8f0', borderRadius: '6px', background: 'white' }}
            >
              <option value="">{t('calendar.allDoctors')}</option>
              {vets.map(v => (
                <option key={v.id} value={v.id}>{v.first_name} {v.last_name}</option>
              ))}
            </select>
          </div>
        )}
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          <button
            type="button"
            className={viewMode === 'week' ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setViewMode('week')}
            style={{ padding: '0.35rem 0.75rem', fontSize: '0.875rem' }}
          >
            {t('calendar.viewWeek')}
          </button>
          <button
            type="button"
            className={viewMode === 'room' ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setViewMode('room')}
            style={{ padding: '0.35rem 0.75rem', fontSize: '0.875rem' }}
          >
            {t('calendar.viewRoom')}
          </button>
        </div>
        <button className="btn-secondary" onClick={() => navigateWeek(-1)}>{t('calendar.previous')}</button>
        <span className="calendar-month">{monthName}</span>
        <button className="btn-secondary" onClick={() => navigateWeek(1)}>{t('calendar.next')}</button>
      </div>

      <div className="tab-content-wrapper">
        {loading && <div className="loading-message">{t('calendar.loadingCalendar')}</div>}
        {viewMode === 'room' ? (
          <div className="calendar-view">
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '120px repeat(7, 1fr)',
                gap: '1px',
                backgroundColor: '#e2e8f0',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                overflow: 'hidden',
              }}
            >
              <div style={{ padding: '0.5rem', background: '#edf2f7', fontWeight: 600 }}>{t('calendar.room')}</div>
              {weekDates.map((date, idx) => (
                <div key={idx} style={{ padding: '0.5rem', background: '#edf2f7', fontWeight: 600, textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem' }}>{days[date.getDay()]}</div>
                  <div>{date.getDate()}</div>
                </div>
              ))}
              {rooms.map((room) => (
                <React.Fragment key={room.id}>
                  <div style={{ padding: '0.5rem', background: '#f7fafc', borderBottom: '1px solid #e2e8f0', fontWeight: 500 }}>
                    {t('rooms.' + room.name, { defaultValue: room.name })}
                  </div>
                  {weekDates.map((date, dayIdx) => {
                    const cellApts = getAppointmentsForRoomAndDay(room.id, date)
                    const dateStr = date.toISOString().split('T')[0]
                    const dayData = availabilityByRoomByDay[dateStr]
                    const roomData = room.id && dayData?.rooms ? dayData.rooms.find((r) => r.id === room.id) : null
                    return (
                      <div
                        key={`${room.id ?? 'u'}-${dayIdx}`}
                        style={{
                          padding: '0.5rem',
                          minHeight: '80px',
                          backgroundColor: roomData?.closed_reason ? '#fef2f2' : '#fff',
                          borderBottom: '1px solid #e2e8f0',
                        }}
                        title={roomData?.closed_reason || (cellApts.length ? `${cellApts.length} ${t('calendar.appointments')}` : t('calendar.available'))}
                      >
                        {cellApts.map((apt) => {
                          let displayReason = apt.reason || t('visits.visit')
                          if (displayReason.startsWith('Unknown - ')) displayReason = displayReason.replace('Unknown - ', '')
                          return (
                            <div
                              key={apt.id}
                              className="calendar-event"
                              role="button"
                              tabIndex={0}
                              onClick={(e) => { e.stopPropagation(); setSelectedAppointment(apt); setIsDetailsModalOpen(true) }}
                              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedAppointment(apt); setIsDetailsModalOpen(true) } }}
                              style={{ cursor: 'pointer', marginBottom: '0.25rem' }}
                            >
                              <span className="event-time">{formatTime(apt.starts_at)}</span>
                              <span className="event-title">{displayReason}</span>
                            </div>
                          )
                        })}
                        {roomData?.closed_reason && cellApts.length === 0 && (
                          <span style={{ fontSize: '0.75rem', color: '#718096' }}>{roomData.closed_reason}</span>
                        )}
                      </div>
                    )
                  })}
                </React.Fragment>
              ))}
            </div>
          </div>
        ) : (
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
                      const cellDuties = getDutyForCell(date, hour)

                      return (
                        <div
                          key={`${dayIdx}-${hour}`}
                          className={`calendar-cell calendar-cell-${cellStatus}`}
                          title={cellStatus === 'unavailable' ? t('calendar.notAvailable') : cellStatus === 'busy' ? t('calendar.busy') : t('calendar.available')}
                          onClick={() => handleCellClick(date, hour)}
                          style={{ cursor: 'pointer' }}
                        >
                          {cellDuties.map((duty) => (
                            <div
                              key={`duty-${duty.id}`}
                              style={{
                                background: '#3182ce',
                                color: '#fff',
                                borderRadius: '4px',
                                padding: '2px 4px',
                                fontSize: '0.72rem',
                                fontWeight: 600,
                                marginBottom: '2px',
                                pointerEvents: 'none',
                              }}
                            >
                              {t('scheduler.onDuty')} {duty.start_time.slice(0, 5)}–{duty.end_time.slice(0, 5)}
                            </div>
                          ))}
                          {cellAppointments.map((apt) => {
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
                                {apt.room && (
                                  <span className="event-room" style={{ fontSize: '0.7rem', opacity: 0.9 }}>{t('rooms.' + apt.room.name, { defaultValue: apt.room.name })}</span>
                                )}
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
        )}
      </div>

      <VisitDetailsModal
        isOpen={isDetailsModalOpen}
        onClose={() => {
          setIsDetailsModalOpen(false)
          setSelectedAppointment(null)
        }}
        appointment={selectedAppointment}
        onStartVisit={onStartVisit}
      />

      <AddAppointmentModal
        isOpen={isStartVisitModalOpen}
        initialStartsAt={clickedSlotTime}
        onClose={() => { setIsStartVisitModalOpen(false); setClickedSlotTime(null) }}
        onSuccess={() => {
          setIsStartVisitModalOpen(false)
          setClickedSlotTime(null)
          fetchAppointments()
        }}
      />
    </div>
  )
}

export default CalendarTab
