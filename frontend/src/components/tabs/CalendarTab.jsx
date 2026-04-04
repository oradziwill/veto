import { useState, useEffect, Fragment } from 'react'
import { useTranslation } from 'react-i18next'
import { appointmentsAPI, availabilityAPI, roomsAPI, schedulerAPI } from '../../services/api'
import VisitDetailsModal from '../modals/VisitDetailsModal'
import AddAppointmentModal from '../modals/AddAppointmentModal'
import './CalendarTab.css'

const DUTY_COLORS = [
  '#3b82f6', '#16a34a', '#d97706', '#ef4444', '#8b5cf6',
  '#f97316', '#0d9488', '#ec4899', '#2563eb', '#15803d',
]

const getDutyColor = (vetId) => DUTY_COLORS[(vetId || 0) % DUTY_COLORS.length]

const HOURS = Array.from({ length: 12 }, (_, i) => i + 8) // 8–19

const CalendarTab = ({ vets = null, vetId = null, onVetChange = null, onStartVisit = null, currentUserId = null, userRole = null }) => {
  const { t, i18n } = useTranslation()
  const [appointments, setAppointments] = useState([])
  const [rooms, setRooms] = useState([])
  const [viewMode, setViewMode] = useState('week')
  const [selectedAppointment, setSelectedAppointment] = useState(null)
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [clickedSlotTime, setClickedSlotTime] = useState(null)
  const [loading, setLoading] = useState(true)
  const [currentDate, setCurrentDate] = useState(new Date())
  const [clinicHours, setClinicHours] = useState([])
  const [availabilityByRoomByDay, setAvailabilityByRoomByDay] = useState({})
  const [dutyAssignments, setDutyAssignments] = useState([])

  const locale = i18n.language === 'pl' ? 'pl-PL' : 'en-US'
  const DAY_NAMES = [t('calendar.sun'), t('calendar.mon'), t('calendar.tue'), t('calendar.wed'), t('calendar.thu'), t('calendar.fri'), t('calendar.sat')]

  const getWeekStart = (date) => {
    const d = new Date(date)
    const day = d.getDay()
    const diff = d.getDate() - day + (day === 0 ? -6 : 1) // Monday = start
    return new Date(d.setDate(diff))
  }

  const getWeekDates = (date) => {
    const ws = getWeekStart(date)
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(ws)
      d.setDate(d.getDate() + i)
      return d
    })
  }

  const formatDateTimeLocal = (date) => {
    const pad = (n) => String(n).padStart(2, '0')
    return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
  }

  const fetchAppointments = async () => {
    try {
      setLoading(true)
      const weekStart = getWeekStart(currentDate)
      weekStart.setHours(0, 0, 0, 0)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekEnd.getDate() + 7)
      weekEnd.setHours(23, 59, 59, 999)

      let params = {}
      if (userRole === 'doctor') {
        if (currentUserId) params.vet = currentUserId
      } else {
        if (vetId) params.vet = vetId
      }
      const res = await appointmentsAPI.list(params)
      const all = (res.data.results || res.data || []).filter(apt => {
        const d = new Date(apt.starts_at)
        return d >= weekStart && d < weekEnd
      })
      setAppointments(all)
    } catch {
      setAppointments([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const fetchAll = async () => {
      fetchAppointments()

      try {
        const res = await schedulerAPI.listClinicHours()
        setClinicHours(res.data.results || res.data || [])
      } catch { setClinicHours([]) }

      try {
        const roomsRes = await roomsAPI.list()
        setRooms(roomsRes.data.results || roomsRes.data || [])
        const weekDates = getWeekDates(currentDate)
        const map = {}
        await Promise.all(weekDates.map(async (date) => {
          const dateStr = date.toISOString().split('T')[0]
          try {
            const r = await availabilityAPI.rooms({ date: dateStr })
            map[dateStr] = r.data
          } catch { map[dateStr] = { rooms: [] } }
        }))
        setAvailabilityByRoomByDay(map)
      } catch { setRooms([]) }

      const ws = getWeekStart(currentDate)
      const we = new Date(ws)
      we.setDate(we.getDate() + 6)
      try {
        const res = await schedulerAPI.listAssignments({
          from: ws.toISOString().split('T')[0],
          to: we.toISOString().split('T')[0],
        })
        setDutyAssignments(res.data.results || res.data || [])
      } catch { setDutyAssignments([]) }
    }
    fetchAll()
  }, [currentDate, vetId, currentUserId])

  const weekDates = getWeekDates(currentDate)
  const today = new Date()
  const isToday = (date) =>
    date.getDate() === today.getDate() &&
    date.getMonth() === today.getMonth() &&
    date.getFullYear() === today.getFullYear()

  const monthLabel = currentDate.toLocaleDateString(locale, { month: 'long', year: 'numeric' })

  const aptForCell = (date, hour) =>
    appointments.filter(apt => {
      const s = new Date(apt.starts_at)
      const e = apt.ends_at ? new Date(apt.ends_at) : new Date(s.getTime() + 30 * 60 * 1000)
      if (s.getDate() !== date.getDate() || s.getMonth() !== date.getMonth() || s.getFullYear() !== date.getFullYear()) return false
      const hs = new Date(date); hs.setHours(hour, 0, 0, 0)
      const he = new Date(hs); he.setHours(hour + 1, 0, 0, 0)
      return s < he && e > hs
    })

  const aptForRoomDay = (roomId, date) =>
    appointments.filter(apt => {
      const d = new Date(apt.starts_at)
      return d.getDate() === date.getDate() && d.getMonth() === date.getMonth() && d.getFullYear() === date.getFullYear() && (apt.room?.id ?? null) === roomId
    })

  const cellStatus = (date, hour) => {
    const jsDay = date.getDay()
    const weekday = jsDay === 0 ? 6 : jsDay - 1
    const clinicDay = clinicHours.find(h => h.weekday === weekday && h.is_active)
    if (!clinicDay) return 'unavailable'
    const [sh] = clinicDay.start_time.split(':').map(Number)
    const [eh] = clinicDay.end_time.split(':').map(Number)
    if (hour < sh || hour >= eh) return 'unavailable'
    return aptForCell(date, hour).length > 0 ? 'busy' : 'free'
  }

  const formatTime = (ds) => new Date(ds).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', hour12: false })

  const dutiesForDay = (date) => {
    const ds = date.toISOString().split('T')[0]
    return dutyAssignments.filter(d => d.date === ds)
  }

  const handleCellClick = (date, hour) => {
    const d = new Date(date)
    d.setHours(hour, 0, 0, 0)
    setClickedSlotTime(formatDateTimeLocal(d))
    setIsAddModalOpen(true)
  }

  const cleanReason = (r) => (r || t('visits.visit')).replace('Unknown - ', '')

  return (
    <div className="cal-root">
      {/* Toolbar */}
      <div className="cal-toolbar">
        <div className="cal-toolbar-left">
          {vets && userRole !== 'doctor' && (
            <div className="cal-vet-filter">
              <label>{t('calendar.doctor')}</label>
              <select
                value={vetId || ''}
                onChange={e => onVetChange(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">{t('calendar.allDoctors')}</option>
                {vets.map(v => (
                  <option key={v.id} value={v.id}>{v.first_name} {v.last_name}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="cal-toolbar-center">
          <button className="cal-nav-btn" onClick={() => { const d = new Date(currentDate); d.setDate(d.getDate() - 7); setCurrentDate(d) }}>‹</button>
          <span className="cal-month-label">{monthLabel}</span>
          <button className="cal-nav-btn" onClick={() => { const d = new Date(currentDate); d.setDate(d.getDate() + 7); setCurrentDate(d) }}>›</button>
          <button className="cal-today-btn" onClick={() => setCurrentDate(new Date())}>{t('calendar.today')}</button>
        </div>

        <div className="cal-toolbar-right">
          <div className="cal-view-toggle">
            <button
              className={viewMode === 'week' ? 'active' : ''}
              onClick={() => setViewMode('week')}
            >{t('calendar.viewWeek')}</button>
            <button
              className={viewMode === 'room' ? 'active' : ''}
              onClick={() => setViewMode('room')}
            >{t('calendar.viewRoom')}</button>
          </div>
          <button className="cal-add-btn" onClick={() => setIsAddModalOpen(true)}>{t('visits.newVisit')}</button>
        </div>
      </div>

      {loading && <div className="cal-loading">{t('calendar.loadingCalendar')}</div>}

      {/* Week view — single unified grid so header and body columns always align */}
      {viewMode === 'week' && (
        <div className="cal-week">
          <div className="cal-week-grid">
            {/* Row 1: sticky header */}
            <div className="cal-time-gutter" />
            {weekDates.map((date, i) => {
              const duties = dutiesForDay(date)
              const tod = isToday(date)
              return (
                <div key={i} className={`cal-day-head${tod ? ' cal-day-head--today' : ''}`}>
                  <div className="cal-day-name">{DAY_NAMES[date.getDay()]}</div>
                  <div className={`cal-day-num${tod ? ' cal-day-num--today' : ''}`}>{date.getDate()}</div>
                  {duties.map(d => (
                    <div key={d.id} className="cal-duty-badge" style={{ background: getDutyColor(d.vet) }}>
                      <span className="cal-duty-name">{d.vet_name}</span>
                      <span className="cal-duty-time">{d.start_time.slice(0,5)}–{d.end_time.slice(0,5)}</span>
                    </div>
                  ))}
                </div>
              )
            })}

            {/* Rows 2–13: hour slots */}
            {HOURS.map(hour => (
              <Fragment key={hour}>
                <div className="cal-hour-label">{hour}:00</div>
                {weekDates.map((date, di) => {
                  const apts = aptForCell(date, hour)
                  const status = cellStatus(date, hour)
                  const tod = isToday(date)
                  return (
                    <div
                      key={di}
                      className={`cal-cell cal-cell--${status}${tod ? ' cal-cell--today' : ''}`}
                      onClick={() => status !== 'unavailable' && handleCellClick(date, hour)}
                    >
                      {apts.map(apt => (
                        <div
                          key={apt.id}
                          className="cal-event"
                          onClick={e => { e.stopPropagation(); setSelectedAppointment(apt); setIsDetailsModalOpen(true) }}
                        >
                          <span className="cal-event-time">{formatTime(apt.starts_at)}</span>
                          <span className="cal-event-title">{cleanReason(apt.reason)}</span>
                        </div>
                      ))}
                    </div>
                  )
                })}
              </Fragment>
            ))}
          </div>
        </div>
      )}

      {/* Room view */}
      {viewMode === 'room' && (
        <div className="cal-room">
          <div className="cal-room-grid" style={{ gridTemplateColumns: `140px repeat(${weekDates.length}, 1fr)` }}>
            <div className="cal-room-corner">{t('calendar.room')}</div>
            {weekDates.map((date, i) => (
              <div key={i} className={`cal-day-head${isToday(date) ? ' cal-day-head--today' : ''}`}>
                <div className="cal-day-name">{DAY_NAMES[date.getDay()]}</div>
                <div className={`cal-day-num${isToday(date) ? ' cal-day-num--today' : ''}`}>{date.getDate()}</div>
              </div>
            ))}
            {rooms.map(room => (
              <Fragment key={room.id}>
                <div className="cal-room-label">{t('rooms.' + room.name, { defaultValue: room.name })}</div>
                {weekDates.map((date, di) => {
                  const apts = aptForRoomDay(room.id, date)
                  const ds = date.toISOString().split('T')[0]
                  const roomData = availabilityByRoomByDay[ds]?.rooms?.find(r => r.id === room.id)
                  return (
                    <div key={di} className={`cal-room-cell${roomData?.closed_reason ? ' cal-room-cell--closed' : ''}`}>
                      {apts.map(apt => (
                        <div
                          key={apt.id}
                          className="cal-event"
                          onClick={() => { setSelectedAppointment(apt); setIsDetailsModalOpen(true) }}
                        >
                          <span className="cal-event-time">{formatTime(apt.starts_at)}</span>
                          <span className="cal-event-title">{cleanReason(apt.reason)}</span>
                        </div>
                      ))}
                      {roomData?.closed_reason && !apts.length && (
                        <span className="cal-room-closed">{roomData.closed_reason}</span>
                      )}
                    </div>
                  )
                })}
              </Fragment>
            ))}
          </div>
        </div>
      )}

      <VisitDetailsModal
        isOpen={isDetailsModalOpen}
        onClose={() => { setIsDetailsModalOpen(false); setSelectedAppointment(null) }}
        appointment={selectedAppointment}
        onStartVisit={onStartVisit}
      />

      <AddAppointmentModal
        isOpen={isAddModalOpen}
        initialStartsAt={clickedSlotTime}
        onClose={() => { setIsAddModalOpen(false); setClickedSlotTime(null) }}
        onSuccess={() => { setIsAddModalOpen(false); setClickedSlotTime(null); fetchAppointments() }}
      />
    </div>
  )
}

export default CalendarTab
