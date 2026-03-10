import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { vetsAPI, schedulerAPI } from '../../services/api'

// ─── helpers ──────────────────────────────────────────────────────────────────

const toISO = (d) => d.toISOString().split('T')[0]
const formatTime = (t) => (t ? t.slice(0, 5) : '')
const WEEKDAY_KEYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
const WEEKDAY_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

// Doctor palette — up to 12 doctors get distinct pastel colours
const DOC_COLORS = [
  { bg: '#c6f6d5', text: '#276749' },
  { bg: '#bee3f8', text: '#2c5282' },
  { bg: '#fbb6ce', text: '#97266d' },
  { bg: '#fefcbf', text: '#744210' },
  { bg: '#e9d8fd', text: '#553c9a' },
  { bg: '#fed7d7', text: '#9b2c2c' },
  { bg: '#b2f5ea', text: '#234e52' },
  { bg: '#fbd38d', text: '#7b341e' },
  { bg: '#d6bcfa', text: '#44337a' },
  { bg: '#9decf9', text: '#065666' },
  { bg: '#f9a8d4', text: '#831843' },
  { bg: '#a7f3d0', text: '#064e3b' },
]

function getDocColor(idx) {
  return DOC_COLORS[idx % DOC_COLORS.length]
}

// ─── ClinicHoursSetup ─────────────────────────────────────────────────────────

const inputStyle = {
  border: '1px solid #cbd5e0', borderRadius: '4px',
  padding: '0.25rem 0.4rem', fontSize: '0.85rem',
}

const ClinicHoursSetup = ({ clinicHours, onRefresh }) => {
  const { t } = useTranslation()
  // Local state: weekday → { active, start, end, existingId }
  const [schedule, setSchedule] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    const s = {}
    for (let d = 0; d <= 6; d++) {
      const wh = clinicHours.find((h) => h.weekday === d)
      s[d] = {
        active: !!wh?.is_active,
        start: wh ? formatTime(wh.start_time) : '08:00',
        end: wh ? formatTime(wh.end_time) : '18:00',
        shiftHours: wh?.shift_hours != null ? String(wh.shift_hours) : '',
        existingId: wh?.id || null,
      }
    }
    setSchedule(s)
  }, [clinicHours])

  const toggle = (d) => setSchedule((p) => ({ ...p, [d]: { ...p[d], active: !p[d].active } }))
  const setTime = (d, field, val) => setSchedule((p) => ({ ...p, [d]: { ...p[d], [field]: val } }))
  const setShift = (d, val) => setSchedule((p) => ({ ...p, [d]: { ...p[d], shiftHours: val } }))

  const handleSave = async () => {
    setSaving(true); setError(null); setSuccess(false)
    try {
      await Promise.all(Object.entries(schedule).map(async ([day, cfg]) => {
        const weekday = Number(day)
        if (cfg.active) {
          const payload = {
            weekday,
            start_time: cfg.start,
            end_time: cfg.end,
            is_active: true,
            shift_hours: cfg.shiftHours ? Number(cfg.shiftHours) : null,
          }
          if (cfg.existingId) await schedulerAPI.updateClinicHours(cfg.existingId, payload)
          else await schedulerAPI.createClinicHours(payload)
        } else if (cfg.existingId) {
          await schedulerAPI.deleteClinicHours(cfg.existingId)
        }
      }))
      setSuccess(true)
      onRefresh()
      setTimeout(() => setSuccess(false), 2500)
    } catch (err) {
      const data = err.response?.data
      setError(data ? Object.values(data).flat().join(' ') : t('planner.saveError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <p style={{ color: '#718096', fontSize: '0.9rem', marginBottom: '1rem' }}>
        {t('planner.clinicHoursHint')}
      </p>
      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{t('planner.saved')}</div>}
      <div className="inventory-table">
        <table>
          <thead>
            <tr>
              <th>{t('scheduler.day')}</th>
              <th>{t('planner.open')}</th>
              <th>{t('scheduler.startTime')}</th>
              <th>{t('scheduler.endTime')}</th>
              <th>{t('planner.shiftDuration')}</th>
            </tr>
          </thead>
          <tbody>
            {WEEKDAY_KEYS.map((key, d) => (
              <tr key={d} style={{ opacity: schedule[d]?.active ? 1 : 0.5 }}>
                <td style={{ fontWeight: '500', width: '120px' }}>{t(`scheduler.${key}`)}</td>
                <td style={{ width: '70px' }}>
                  <input type="checkbox" checked={!!schedule[d]?.active} onChange={() => toggle(d)} />
                </td>
                <td>
                  <input type="time" style={inputStyle} value={schedule[d]?.start || '08:00'}
                    disabled={!schedule[d]?.active}
                    onChange={(e) => setTime(d, 'start', e.target.value)} />
                </td>
                <td>
                  <input type="time" style={inputStyle} value={schedule[d]?.end || '18:00'}
                    disabled={!schedule[d]?.active}
                    onChange={(e) => setTime(d, 'end', e.target.value)} />
                </td>
                <td>
                  <select
                    style={inputStyle}
                    value={schedule[d]?.shiftHours || ''}
                    disabled={!schedule[d]?.active}
                    onChange={(e) => setShift(d, e.target.value)}
                  >
                    <option value="">{t('planner.fullDay')}</option>
                    <option value="4">4h</option>
                    <option value="6">6h</option>
                    <option value="8">8h</option>
                    <option value="10">10h</option>
                    <option value="12">12h</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ color: '#a0aec0', fontSize: '0.8rem', marginTop: '0.5rem' }}>
        {t('planner.shiftHint')}
      </p>
      <div style={{ marginTop: '0.75rem' }}>
        <button className="btn-primary" disabled={saving} onClick={handleSave}>
          {saving ? t('common.saving') : t('common.save')}
        </button>
      </div>
    </div>
  )
}

// ─── Generate controls ─────────────────────────────────────────────────────────

const todayISO = () => toISO(new Date())
const sixMonthsISO = () => {
  const d = new Date()
  d.setMonth(d.getMonth() + 6)
  return toISO(d)
}

const GenerateControls = ({ clinicHours, onGenerated }) => {
  const { t } = useTranslation()
  const [startDate, setStartDate] = useState(todayISO)
  const [endDate, setEndDate] = useState(sixMonthsISO)
  const [overwrite, setOverwrite] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const openDays = clinicHours.filter((h) => h.is_active).length

  const handleGenerate = async () => {
    setGenerating(true); setError(null); setResult(null)
    try {
      const res = await schedulerAPI.generate({ start_date: startDate, end_date: endDate, overwrite })
      setResult(res.data)
      onGenerated()
    } catch (err) {
      const data = err.response?.data
      setError(data?.detail || (data && Object.values(data).flat().join(' ')) || t('planner.generateError'))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div style={{ background: '#f7fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '1.25rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div>
          <label style={{ fontSize: '0.8rem', fontWeight: '500', display: 'block', marginBottom: '3px' }}>{t('planner.from')}</label>
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label style={{ fontSize: '0.8rem', fontWeight: '500', display: 'block', marginBottom: '3px' }}>{t('planner.to')}</label>
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={inputStyle} />
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', cursor: 'pointer', paddingBottom: '2px' }}>
          <input type="checkbox" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} />
          {t('planner.overwrite')}
        </label>
        <button className="btn-primary" disabled={generating || openDays === 0} onClick={handleGenerate}
          style={{ whiteSpace: 'nowrap' }}>
          {generating ? t('planner.generating') : t('planner.generate')}
        </button>
      </div>
      {openDays === 0 && (
        <div style={{ marginTop: '0.75rem', color: '#b7791f', fontSize: '0.85rem' }}>
          {t('planner.noClinicHours')}
        </div>
      )}
      {error && <div className="error-message" style={{ marginTop: '0.75rem' }}>{error}</div>}
      {result && (
        <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#f0fff4', borderRadius: '6px', fontSize: '0.85rem', color: '#276749' }}>
          <strong>{t('planner.generated')}: {result.created}</strong>
          {result.skipped_existing > 0 && <span style={{ marginLeft: '1rem', color: '#718096' }}>{t('planner.skippedExisting')}: {result.skipped_existing}</span>}
          {result.skipped_no_doctors > 0 && <span style={{ marginLeft: '1rem', color: '#c53030' }}>{t('planner.uncovered')}: {result.skipped_no_doctors}</span>}
          {result.uncovered_dates?.length > 0 && (
            <div style={{ marginTop: '0.4rem', color: '#c53030' }}>
              {t('planner.uncoveredDates')}: {result.uncovered_dates.slice(0, 5).join(', ')}{result.uncovered_dates.length > 5 ? ` +${result.uncovered_dates.length - 5}` : ''}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Day edit popover ─────────────────────────────────────────────────────────

const DayEditPopover = ({ date, assignments, vets, onClose, onRefresh }) => {
  const { t } = useTranslation()
  const ref = useRef(null)
  const [form, setForm] = useState({ vet: '', start_time: '08:00', end_time: '18:00', note: '' })
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [error, setError] = useState(null)

  // Close when clicking outside
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose() }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const handleAdd = async () => {
    if (!form.vet) { setError(t('planner.selectDoctor')); return }
    setSaving(true); setError(null)
    try {
      await schedulerAPI.createAssignment({ vet: Number(form.vet), date, start_time: form.start_time, end_time: form.end_time, note: form.note })
      setForm({ vet: '', start_time: '08:00', end_time: '18:00', note: '' })
      onRefresh()
    } catch (err) {
      const data = err.response?.data
      setError(data ? Object.values(data).flat().join(' ') : t('planner.saveError'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    setDeletingId(id)
    try {
      await schedulerAPI.deleteAssignment(id)
      onRefresh()
    } finally {
      setDeletingId(null)
    }
  }

  const dayAssignments = assignments[date] || []
  const assignedVetIds = new Set(dayAssignments.map((a) => a.vet))
  const availableVets = vets.filter((v) => !assignedVetIds.has(v.id))

  return (
    <div ref={ref} style={{
      position: 'absolute', zIndex: 200, background: 'white',
      boxShadow: '0 8px 24px rgba(0,0,0,0.15)', borderRadius: '10px',
      border: '1px solid #e2e8f0', padding: '1rem', minWidth: '280px',
      top: '100%', left: '50%', transform: 'translateX(-50%)',
    }}>
      <div style={{ fontWeight: '600', marginBottom: '0.75rem', color: '#2d3748' }}>{date}</div>

      {dayAssignments.length > 0 && (
        <div style={{ marginBottom: '0.75rem' }}>
          {dayAssignments.map((a) => (
            <div key={a.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.3rem 0.5rem', borderRadius: '6px', background: '#f7fafc', marginBottom: '0.3rem' }}>
              <span style={{ fontSize: '0.85rem' }}>
                <strong>{a.vet_name}</strong>
                <span style={{ color: '#718096', marginLeft: '0.4rem' }}>{formatTime(a.start_time)}–{formatTime(a.end_time)}</span>
              </span>
              <button className="btn-link" style={{ color: '#e53e3e', fontSize: '0.75rem', marginLeft: '0.5rem' }}
                disabled={deletingId === a.id} onClick={() => handleDelete(a.id)}>✕</button>
            </div>
          ))}
        </div>
      )}

      {availableVets.length > 0 ? (
        <div style={{ borderTop: dayAssignments.length > 0 ? '1px solid #e2e8f0' : 'none', paddingTop: dayAssignments.length > 0 ? '0.75rem' : 0 }}>
          <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#718096', marginBottom: '0.4rem', textTransform: 'uppercase' }}>{t('planner.addDoctor')}</div>
          <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.4rem' }}>
            <select value={form.vet} onChange={(e) => setForm((p) => ({ ...p, vet: e.target.value }))} style={{ ...inputStyle, flex: 1 }}>
              <option value="">— {t('scheduler.doctor')} —</option>
              {availableVets.map((v) => <option key={v.id} value={v.id}>{v.first_name} {v.last_name}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.4rem' }}>
            <input type="time" value={form.start_time} onChange={(e) => setForm((p) => ({ ...p, start_time: e.target.value }))} style={{ ...inputStyle, flex: 1 }} />
            <span style={{ alignSelf: 'center', color: '#718096' }}>–</span>
            <input type="time" value={form.end_time} onChange={(e) => setForm((p) => ({ ...p, end_time: e.target.value }))} style={{ ...inputStyle, flex: 1 }} />
          </div>
          {error && <div style={{ color: '#c53030', fontSize: '0.75rem', marginBottom: '0.4rem' }}>{error}</div>}
          <button className="btn-primary" style={{ width: '100%', padding: '0.35rem' }} disabled={saving} onClick={handleAdd}>
            {saving ? '…' : t('planner.assignDoctor')}
          </button>
        </div>
      ) : (
        <div style={{ fontSize: '0.8rem', color: '#718096', borderTop: dayAssignments.length > 0 ? '1px solid #e2e8f0' : 'none', paddingTop: dayAssignments.length > 0 ? '0.5rem' : 0 }}>
          {t('planner.allAssigned')}
        </div>
      )}
    </div>
  )
}

// ─── Month Calendar ───────────────────────────────────────────────────────────

const MonthCalendar = ({ assignments, clinicHours, holidays, vets, onRefresh }) => {
  const { t } = useTranslation()
  const [currentMonth, setCurrentMonth] = useState(() => {
    const d = new Date(); return { year: d.getFullYear(), month: d.getMonth() }
  })
  const [openDay, setOpenDay] = useState(null)

  const { year, month } = currentMonth
  const monthLabel = new Date(year, month, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

  const prevMonth = () => setCurrentMonth(({ year, month }) =>
    month === 0 ? { year: year - 1, month: 11 } : { year, month: month - 1 })
  const nextMonth = () => setCurrentMonth(({ year, month }) =>
    month === 11 ? { year: year + 1, month: 0 } : { year, month: month + 1 })

  // Build calendar grid: 6 weeks × 7 days
  const firstDay = new Date(year, month, 1)
  const startDay = new Date(firstDay)
  const jsDay = startDay.getDay()
  startDay.setDate(startDay.getDate() - (jsDay === 0 ? 6 : jsDay - 1)) // start on Monday

  const days = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(startDay)
    d.setDate(d.getDate() + i)
    return d
  })

  // Index assignments by date
  // assignments is already a dict: date → [assignment, ...]

  // Index holidays
  const holidayDates = new Set(holidays.map((h) => h.date))
  const openWeekdays = new Set(clinicHours.filter((h) => h.is_active).map((h) => h.weekday))

  // Doctor colour map
  const doctorColorMap = {}
  vets.forEach((v, i) => { doctorColorMap[v.id] = getDocColor(i) })

  const today = toISO(new Date())

  return (
    <div>
      {/* Legend */}
      {vets.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
          {vets.map((v, i) => {
            const c = getDocColor(i)
            return (
              <span key={v.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem' }}>
                <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: c.bg, border: `1px solid ${c.text}40` }} />
                {v.first_name} {v.last_name}
              </span>
            )
          })}
        </div>
      )}

      {/* Month nav */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.75rem' }}>
        <button className="btn-secondary" onClick={prevMonth} style={{ padding: '0.3rem 0.8rem' }}>‹</button>
        <span style={{ fontWeight: '600', minWidth: '160px', textAlign: 'center' }}>{monthLabel}</span>
        <button className="btn-secondary" onClick={nextMonth} style={{ padding: '0.3rem 0.8rem' }}>›</button>
        <button className="btn-secondary" onClick={() => setCurrentMonth({ year: new Date().getFullYear(), month: new Date().getMonth() })}
          style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }}>{t('scheduler.today')}</button>
      </div>

      {/* Calendar grid */}
      <div style={{ border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', background: '#f7fafc', borderBottom: '1px solid #e2e8f0' }}>
          {WEEKDAY_SHORT.map((d, i) => (
            <div key={i} style={{ padding: '0.5rem', textAlign: 'center', fontSize: '0.8rem', fontWeight: '600', color: i >= 5 ? '#a0aec0' : '#4a5568' }}>{d}</div>
          ))}
        </div>
        {/* Weeks */}
        {Array.from({ length: 6 }, (_, week) => (
          <div key={week} style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', borderBottom: week < 5 ? '1px solid #e2e8f0' : 'none' }}>
            {days.slice(week * 7, week * 7 + 7).map((day, dayIdx) => {
              const iso = toISO(day)
              const inMonth = day.getMonth() === month
              const isToday = iso === today
              const isHoliday = holidayDates.has(iso)
              const weekday = day.getDay() === 0 ? 6 : day.getDay() - 1
              const clinicOpen = openWeekdays.has(weekday)
              const dayAssignments = assignments[iso] || []
              const isOpen = openDay === iso

              return (
                <div key={dayIdx}
                  style={{
                    minHeight: '80px', padding: '0.4rem', position: 'relative',
                    borderRight: dayIdx < 6 ? '1px solid #e2e8f0' : 'none',
                    background: !inMonth ? '#fafafa' : isHoliday ? '#ebf8ff' : !clinicOpen ? '#f7fafc' : 'white',
                    cursor: inMonth && clinicOpen && !isHoliday ? 'pointer' : 'default',
                  }}
                  onClick={() => {
                    if (!inMonth || !clinicOpen || isHoliday) return
                    setOpenDay(isOpen ? null : iso)
                  }}>
                  {/* Day number */}
                  <div style={{
                    fontSize: '0.8rem', fontWeight: isToday ? '700' : '400',
                    color: !inMonth ? '#cbd5e0' : isHoliday ? '#2b6cb0' : !clinicOpen ? '#a0aec0' : isToday ? 'white' : '#4a5568',
                    width: '22px', height: '22px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    borderRadius: '50%', background: isToday ? '#3182ce' : 'transparent',
                    marginBottom: '0.25rem',
                  }}>
                    {day.getDate()}
                  </div>

                  {/* Status indicators */}
                  {inMonth && isHoliday && (
                    <div style={{ fontSize: '0.7rem', color: '#2b6cb0', marginBottom: '0.2rem' }}>{t('scheduler.holiday')}</div>
                  )}
                  {inMonth && !clinicOpen && !isHoliday && (
                    <div style={{ fontSize: '0.7rem', color: '#a0aec0' }}>{t('planner.closed')}</div>
                  )}
                  {inMonth && clinicOpen && !isHoliday && dayAssignments.length === 0 && (
                    <div style={{ fontSize: '0.7rem', color: '#e53e3e', fontStyle: 'italic' }}>{t('planner.noCover')}</div>
                  )}

                  {/* Assignment badges */}
                  {dayAssignments.map((a) => {
                    const vetIdx = vets.findIndex((v) => v.id === a.vet)
                    const color = vetIdx >= 0 ? getDocColor(vetIdx) : { bg: '#e2e8f0', text: '#4a5568' }
                    return (
                      <div key={a.id} style={{
                        fontSize: '0.7rem', padding: '1px 5px', borderRadius: '4px',
                        background: color.bg, color: color.text, marginBottom: '2px',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                        {a.vet_name.split(' ')[0]}
                        <span style={{ opacity: 0.7, marginLeft: '3px' }}>{formatTime(a.start_time)}–{formatTime(a.end_time)}</span>
                      </div>
                    )
                  })}

                  {/* Edit popover */}
                  {isOpen && (
                    <DayEditPopover
                      date={iso}
                      assignments={assignments}
                      vets={vets}
                      onClose={() => setOpenDay(null)}
                      onRefresh={() => { setOpenDay(null); onRefresh() }}
                    />
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Main SchedulePlannerTab ──────────────────────────────────────────────────

const PLAN_TABS = ['clinicHours', 'calendar']

const SchedulePlannerTab = () => {
  const { t } = useTranslation()
  const [planTab, setPlanTab] = useState('clinicHours')
  const [vets, setVets] = useState([])
  const [clinicHours, setClinicHours] = useState([])
  const [assignmentsRaw, setAssignmentsRaw] = useState([])
  const [holidays, setHolidays] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Convert raw assignment array to date-indexed dict
  const assignments = assignmentsRaw.reduce((acc, a) => {
    if (!acc[a.date]) acc[a.date] = []
    acc[a.date].push(a)
    return acc
  }, {})

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      // Fetch assignments for the next 13 months (generous window)
      const today = new Date()
      const fromISO = toISO(today)
      const futureDate = new Date(today); futureDate.setMonth(futureDate.getMonth() + 13)
      const toISO_ = toISO(futureDate)

      const [vetsRes, hoursRes, assignRes, holRes] = await Promise.all([
        vetsAPI.list(),
        schedulerAPI.listClinicHours(),
        schedulerAPI.listAssignments({ from: fromISO, to: toISO_ }),
        schedulerAPI.listHolidays(),
      ])
      setVets(vetsRes.data.results || vetsRes.data)
      setClinicHours(hoursRes.data.results || hoursRes.data)
      setAssignmentsRaw(assignRes.data.results || assignRes.data)
      setHolidays(holRes.data.results || holRes.data)
    } catch {
      setError(t('planner.loadError'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => { load() }, [load])

  return (
    <div>
      {/* Sub-nav */}
      <div style={{ display: 'flex', gap: '0.25rem', borderBottom: '2px solid #e2e8f0', marginBottom: '1.5rem' }}>
        {PLAN_TABS.map((tab) => (
          <button key={tab} onClick={() => setPlanTab(tab)} style={{
            padding: '0.4rem 0.9rem', border: 'none', background: 'none', cursor: 'pointer',
            fontSize: '0.85rem',
            color: planTab === tab ? '#3182ce' : '#718096',
            borderBottom: planTab === tab ? '2px solid #3182ce' : '2px solid transparent',
            marginBottom: '-2px',
            fontWeight: planTab === tab ? '600' : '400',
          }}>
            {t(`planner.subtab_${tab}`)}
          </button>
        ))}
      </div>

      {loading && <div className="loading-message">{t('common.loading')}</div>}
      {error && <div className="error-message">{error}</div>}

      {!loading && !error && (
        <>
          {planTab === 'clinicHours' && (
            <ClinicHoursSetup clinicHours={clinicHours} onRefresh={load} />
          )}
          {planTab === 'calendar' && (
            <>
              <GenerateControls clinicHours={clinicHours} onGenerated={load} />
              <MonthCalendar
                assignments={assignments}
                clinicHours={clinicHours}
                holidays={holidays}
                vets={vets}
                onRefresh={load}
              />
            </>
          )}
        </>
      )}
    </div>
  )
}

export default SchedulePlannerTab
