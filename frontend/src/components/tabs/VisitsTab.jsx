import { useState, useEffect, Fragment } from 'react'
import { useTranslation } from 'react-i18next'
import { appointmentsAPI, vetsAPI, schedulerAPI } from '../../services/api'
import AddAppointmentModal from '../modals/AddAppointmentModal'
import VisitDetailsModal from '../modals/VisitDetailsModal'
import './VisitsTab.css'

const DEFAULT_HOURS = Array.from({ length: 12 }, (_, i) => i + 8) // 8–19 fallback

const VET_COLORS = [
  '#16a34a', '#2563eb', '#d97706', '#8b5cf6',
  '#ef4444', '#0d9488', '#ec4899', '#f97316',
]

const toDateStr = (d) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const VisitsTab = ({ userRole = null, currentUserId = null }) => {
  const { t, i18n } = useTranslation()
  const locale = i18n.language === 'pl' ? 'pl-PL' : 'en-US'

  const [selectedDate, setSelectedDate] = useState(new Date())
  const [appointments, setAppointments] = useState([])
  const [vets, setVets] = useState([])
  const [loading, setLoading] = useState(true)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [selectedAppointment, setSelectedAppointment] = useState(null)
  const [clinicHours, setClinicHours] = useState([])

  const isAdmin = userRole === 'admin'
  const isReceptionist = userRole === 'receptionist'
  const seesAllVets = isAdmin || isReceptionist

  const dateLabel = selectedDate.toLocaleDateString(locale, {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  })

  const fetchData = async () => {
    setLoading(true)
    try {
      const dateStr = toDateStr(selectedDate)
      const params = { date: dateStr }
      if (!seesAllVets && currentUserId) params.vet = currentUserId

      const [aptsRes, vetsRes] = await Promise.all([
        appointmentsAPI.list(params),
        seesAllVets ? vetsAPI.list() : Promise.resolve(null),
      ])

      const apts = aptsRes.data.results || aptsRes.data || []
      setAppointments(apts)

      if (seesAllVets && vetsRes) {
        setVets(vetsRes.data.results || vetsRes.data || [])
      }
    } catch {
      setAppointments([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [selectedDate, userRole, currentUserId])

  useEffect(() => {
    schedulerAPI.listClinicHours()
      .then(res => setClinicHours(res.data.results || res.data || []))
      .catch(() => setClinicHours([]))
  }, [])

  const gridHours = (() => {
    const active = clinicHours.filter(h => h.is_active)
    if (!active.length) return DEFAULT_HOURS
    const minHour = Math.min(...active.map(h => parseInt(h.start_time.split(':')[0], 10)))
    const maxHour = Math.max(...active.map(h => {
      const [hh, mm] = h.end_time.split(':').map(Number)
      return mm > 0 ? hh + 1 : hh
    }))
    return Array.from({ length: maxHour - minHour }, (_, i) => i + minHour)
  })()

  const changeDate = (delta) => {
    const d = new Date(selectedDate)
    d.setDate(d.getDate() + delta)
    setSelectedDate(d)
  }

  const aptsForHour = (hour, vetId = null) =>
    appointments.filter(apt => {
      const s = new Date(apt.starts_at)
      const e = apt.ends_at ? new Date(apt.ends_at) : new Date(s.getTime() + 30 * 60 * 1000)
      const hs = new Date(selectedDate); hs.setHours(hour, 0, 0, 0)
      const he = new Date(hs); he.setHours(hour + 1, 0, 0, 0)
      const inHour = s < he && e > hs
      if (!inHour) return false
      if (vetId !== null) return (apt.vet?.id ?? apt.vet) === vetId
      return true
    })

  const cleanReason = (r) => (r || t('visits.visit')).replace('Unknown - ', '')

  const formatTime = (ds) =>
    new Date(ds).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', hour12: false })

  const getStatusColor = (status) => {
    if (status === 'completed') return '#15803d'
    if (status === 'cancelled' || status === 'no_show') return '#dc2626'
    return null // use vet color
  }

  // For doctor view: render a single timeline column
  const renderSingleColumn = () => (
    <div className="visits-grid visits-grid--single" style={{ gridTemplateRows: `auto repeat(${gridHours.length}, 60px)` }}>
      <div className="vt-gutter" />
      <div className="vt-col-header vt-col-header--mine">{t('visits.myVisits')}</div>

      {gridHours.map(hour => {
        const apts = aptsForHour(hour)
        return (
          <Fragment key={hour}>
            <div className="vt-hour-label">{hour}:00</div>
            <div className="vt-cell">
              {apts.map(apt => (
                <div
                  key={apt.id}
                  className="vt-event"
                  style={{ background: getStatusColor(apt.status) || VET_COLORS[0] }}
                  onClick={() => setSelectedAppointment(apt)}
                >
                  <span className="vt-event-time">{formatTime(apt.starts_at)}</span>
                  <span className="vt-event-title">{cleanReason(apt.reason)}</span>
                  {apt.patient?.name && (
                    <span className="vt-event-patient">{apt.patient.name}</span>
                  )}
                </div>
              ))}
            </div>
          </Fragment>
        )
      })}
    </div>
  )

  // For admin view: one column per vet
  const renderAdminColumns = () => {
    // Only show vets that have appointments today, plus all vets if none
    const activeVetIds = new Set(appointments.map(a => a.vet?.id ?? a.vet))
    const displayVets = vets.length > 0
      ? (activeVetIds.size > 0 ? vets.filter(v => activeVetIds.has(v.id)) : vets)
      : []

    if (displayVets.length === 0 && !loading) {
      return <div className="vt-empty">{t('visits.noVisitsFound')}</div>
    }

    return (
      <div
        className="visits-grid"
        style={{
          gridTemplateColumns: `56px repeat(${displayVets.length}, minmax(160px, 1fr))`,
          gridTemplateRows: `auto repeat(${gridHours.length}, 60px)`,
        }}
      >
        {/* header row */}
        <div className="vt-gutter" />
        {displayVets.map((vet, i) => (
          <div
            key={vet.id}
            className="vt-col-header"
            style={{ borderBottom: `3px solid ${VET_COLORS[i % VET_COLORS.length]}` }}
          >
            <span
              className="vt-col-dot"
              style={{ background: VET_COLORS[i % VET_COLORS.length] }}
            />
            {vet.first_name} {vet.last_name}
          </div>
        ))}

        {/* hour rows */}
        {gridHours.map(hour => (
          <Fragment key={hour}>
            <div className="vt-hour-label">{hour}:00</div>
            {displayVets.map((vet, i) => {
              const apts = aptsForHour(hour, vet.id)
              return (
                <div key={vet.id} className="vt-cell">
                  {apts.map(apt => (
                    <div
                      key={apt.id}
                      className="vt-event"
                      style={{ background: getStatusColor(apt.status) || VET_COLORS[i % VET_COLORS.length] }}
                      onClick={() => setSelectedAppointment(apt)}
                    >
                      <span className="vt-event-time">{formatTime(apt.starts_at)}</span>
                      <span className="vt-event-title">{cleanReason(apt.reason)}</span>
                      {apt.patient?.name && (
                        <span className="vt-event-patient">{apt.patient.name}</span>
                      )}
                    </div>
                  ))}
                </div>
              )
            })}
          </Fragment>
        ))}
      </div>
    )
  }

  return (
    <div className="vt-root">
      {/* Toolbar */}
      <div className="vt-toolbar">
        <div className="vt-nav">
          <button className="vt-nav-btn" onClick={() => changeDate(-1)}>‹</button>
          <button
            className="vt-date-label"
            onClick={() => setSelectedDate(new Date())}
          >
            {dateLabel}
          </button>
          <button className="vt-nav-btn" onClick={() => changeDate(1)}>›</button>
        </div>
        <button className="vt-add-btn" onClick={() => setIsAddModalOpen(true)}>
          {t('visits.newVisit')}
        </button>
      </div>

      {loading && <div className="vt-loading">{t('visits.loadingVisits')}</div>}

      {!loading && (
        <div className="vt-scroll">
          {seesAllVets ? renderAdminColumns() : renderSingleColumn()}
        </div>
      )}

      <AddAppointmentModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={() => { setIsAddModalOpen(false); fetchData() }}
      />

      <VisitDetailsModal
        isOpen={!!selectedAppointment}
        onClose={() => setSelectedAppointment(null)}
        appointment={selectedAppointment}
      />
    </div>
  )
}

export default VisitsTab
