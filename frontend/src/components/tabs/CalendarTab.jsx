import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { appointmentsAPI, availabilityAPI, roomsAPI, schedulerAPI } from '../../services/api' // availabilityAPI still used by room view
import VisitDetailsModal from '../modals/VisitDetailsModal'
import AddAppointmentModal from '../modals/AddAppointmentModal'
import './Tabs.css'

const DUTY_COLORS = [
  '#3182ce', '#38a169', '#d69e2e', '#e53e3e', '#805ad5',
  '#dd6b20', '#319795', '#d53f8c', '#2b6cb0', '#276749',
]

const getDutyColor = (vetId) => DUTY_COLORS[(vetId || 0) % DUTY_COLORS.length]

const CalendarTab = ({ vets = null, vetId = null, onVetChange = null, onStartVisit = null, currentUserId = null, userRole = null }) => {
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
  const [clinicHours, setClinicHours] = useState([]) // { weekday, start_time, end_time, is_active }
  const [availabilityByRoomByDay, setAvailabilityByRoomByDay] = useState({}) // { 'YYYY-MM-DD': { rooms: [...] } }
  const [dutyAssignments, setDutyAssignments] = useState([])

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

      // Doctor sees only their own visits; reception/admin see all (or filtered by vet dropdown)
      let params = {}
      if (userRole === 'doctor') {
        if (currentUserId) params.vet = currentUserId
      } else {
        if (vetId) params.vet = vetId
      }
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
    const fetchClinicHours = async () => {
      try {
        const res = await schedulerAPI.listClinicHours()
        setClinicHours(res.data.results || res.data || [])
      } catch (err) {
        console.error('Error fetching clinic hours:', err)
        setClinicHours([])
      }
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
      const weekStart = getWeekStart(currentDate)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekEnd.getDate() + 6)
      const from = weekStart.toISOString().split('T')[0]
      const to = weekEnd.toISOString().split('T')[0]
      try {
        // Fetch all doctors' duties — duty calendar is visible to everyone
        const res = await schedulerAPI.listAssignments({ from, to })
        setDutyAssignments(res.data.results || res.data || [])
      } catch (err) {
        console.error('Error fetching duty assignments:', err)
        setDutyAssignments([])
      }
    }

    fetchAppointments()
    fetchClinicHours()
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

  const getDutiesForDay = (date) => {
    const dateStr = date.toISOString().split('T')[0]
    return dutyAssignments.filter(duty => duty.date === dateStr)
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
    // Convert JS day (0=Sun) to API weekday (0=Mon, 6=Sun)
    const jsDay = date.getDay()
    const weekday = jsDay === 0 ? 6 : jsDay - 1

    const clinicDay = clinicHours.find(h => h.weekday === weekday && h.is_active)
    if (!clinicDay) return 'unavailable'

    const [startH] = clinicDay.start_time.split(':').map(Number)
    const [endH] = clinicDay.end_time.split(':').map(Number)
    if (hour < startH || hour >= endH) return 'unavailable'

    if (getAppointmentsForCell(date, hour).length > 0) return 'busy'

    return 'free'
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
        {vets && userRole !== 'doctor' && (
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
              {/* Header row — day names + duty badges */}
              <div className="time-column"></div>
              {weekDates.map((date, idx) => {
                const dayDuties = getDutiesForDay(date)
                return (
                  <div key={idx} className="day-header">
                    <div className="day-name">{days[date.getDay()]}</div>
                    <div className="day-number">{date.getDate()}</div>
                    {dayDuties.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '6px' }}>
                        {dayDuties.map(duty => (
                          <div
                            key={duty.id}
                            style={{
                              background: getDutyColor(duty.vet),
                              color: '#fff',
                              borderRadius: '4px',
                              padding: '2px 6px',
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                          >
                            {duty.vet_name} {duty.start_time.slice(0, 5)}–{duty.end_time.slice(0, 5)}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}

              {/* Hour rows */}
              {hours.map((hour) => (
                <React.Fragment key={hour}>
                  <div className="time-slot">{hour}:00</div>
                  {weekDates.map((date, dayIdx) => {
                    const cellAppointments = getAppointmentsForCell(date, hour)
                    const cellStatus = getCellStatus(date, hour)

                    return (
                      <div
                        key={`${dayIdx}-${hour}`}
                        className={`calendar-cell calendar-cell-${cellStatus}`}
                        title={cellStatus === 'unavailable' ? t('calendar.notAvailable') : cellStatus === 'busy' ? t('calendar.busy') : t('calendar.available')}
                        onClick={() => handleCellClick(date, hour)}
                        style={{ cursor: 'pointer' }}
                      >
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
                </React.Fragment>
              ))}
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
