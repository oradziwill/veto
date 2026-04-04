import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { vetsAPI, schedulerAPI } from '../../services/api'
import SchedulePlannerTab from './SchedulePlannerTab'
import './Tabs.css'

// ─── date helpers ──────────────────────────────────────────────────────────────

const toISO = (date) => date.toISOString().split('T')[0]

const getWeekStart = (date = new Date()) => {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  d.setDate(diff)
  d.setHours(0, 0, 0, 0)
  return d
}

const getWeekDays = (weekStart) =>
  Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart)
    d.setDate(d.getDate() + i)
    return d
  })

const formatTime = (t) => (t ? t.slice(0, 5) : '')
const pad2 = (n) => String(n).padStart(2, '0')
const fmtDate = (d) => `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}`
const WEEKDAY_KEYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

// ─── sub-tab: Week View ────────────────────────────────────────────────────────

// Duty-assignment-aware WeekView
// Priority: holiday > PTO exception > duty assignment > regular working hours
const WeekView = ({ vets, workingHours, exceptions, holidays, assignments }) => {
  const { t } = useTranslation()
  const [weekStart, setWeekStart] = useState(getWeekStart())
  const [loadingWeek, setLoadingWeek] = useState(false)
  const [weekAssignments, setWeekAssignments] = useState(assignments)

  const weekDays = getWeekDays(weekStart)

  // Re-fetch assignments whenever the visible week changes
  useEffect(() => {
    const from = toISO(weekDays[0])
    const to = toISO(weekDays[6])
    setLoadingWeek(true)
    schedulerAPI.listAssignments({ from, to })
      .then((res) => setWeekAssignments(res.data.results || res.data))
      .catch(() => {})
      .finally(() => setLoadingWeek(false))
  }, [weekStart]) // eslint-disable-line react-hooks/exhaustive-deps

  const prevWeek = () => { const d = new Date(weekStart); d.setDate(d.getDate() - 7); setWeekStart(d) }
  const nextWeek = () => { const d = new Date(weekStart); d.setDate(d.getDate() + 7); setWeekStart(d) }

  const holidayDates = new Set(holidays.map((h) => h.date))

  // Build assignment lookup: date → [assignment, ...]
  const assignmentsByDate = weekAssignments.reduce((acc, a) => {
    if (!acc[a.date]) acc[a.date] = []
    acc[a.date].push(a)
    return acc
  }, {})

  const getCellContent = (vet, day) => {
    const iso = toISO(day)

    // 1. Clinic holiday
    if (holidayDates.has(iso)) {
      return { type: 'holiday', lines: [t('scheduler.holiday')] }
    }

    // 2. Vet PTO for this date
    const exc = exceptions.find((e) => e.vet === vet.id && e.date === iso)
    if (exc?.is_day_off) return { type: 'off', lines: [t('scheduler.dayOff')] }

    // 3. Duty assignments — show all shifts this vet is assigned to
    const dayAssignments = (assignmentsByDate[iso] || []).filter((a) => a.vet === vet.id)
    if (dayAssignments.length > 0) {
      return {
        type: 'duty',
        lines: dayAssignments.map((a) => `${formatTime(a.start_time)}–${formatTime(a.end_time)}`),
      }
    }

    // 4. Custom hours exception (not day-off)
    if (exc?.start_time) {
      return { type: 'custom', lines: [`${formatTime(exc.start_time)}–${formatTime(exc.end_time)}`] }
    }

    // 5. Regular working hours (fallback — shown dimmed: plan not yet generated)
    const jsDay = day.getDay()
    const weekday = jsDay === 0 ? 6 : jsDay - 1
    const wh = workingHours.filter((w) => w.vet === vet.id && w.weekday === weekday && w.is_active)
    if (wh.length > 0) {
      return {
        type: 'schedule',
        lines: wh.map((w) => `${formatTime(w.start_time)}–${formatTime(w.end_time)}`),
      }
    }

    return { type: 'none', lines: ['—'] }
  }

  const cellStyle = (type) => {
    if (type === 'duty')     return { background: '#f0fff4', color: '#276749', fontWeight: '600' }
    if (type === 'schedule') return { background: '#f7fafc', color: '#a0aec0' }  // dimmed — no duty assigned yet
    if (type === 'off')      return { background: '#fff5f5', color: '#c53030' }
    if (type === 'holiday')  return { background: '#ebf8ff', color: '#2b6cb0' }
    if (type === 'custom')   return { background: '#fffff0', color: '#744210' }
    return { color: '#e2e8f0' }
  }

  const weekLabel = `${fmtDate(weekDays[0])} – ${fmtDate(weekDays[6])}, ${weekDays[0].getFullYear()}`

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
        <button className="btn-secondary" onClick={prevWeek} style={{ padding: '0.3rem 0.8rem' }}>‹</button>
        <span style={{ fontWeight: '600', minWidth: '180px', textAlign: 'center' }}>{weekLabel}</span>
        <button className="btn-secondary" onClick={nextWeek} style={{ padding: '0.3rem 0.8rem' }}>›</button>
        <button className="btn-secondary" onClick={() => setWeekStart(getWeekStart())} style={{ padding: '0.3rem 0.8rem', fontSize: '0.8rem' }}>
          {t('scheduler.today')}
        </button>
        {loadingWeek && <span style={{ fontSize: '0.8rem', color: '#a0aec0' }}>…</span>}
      </div>

      <div className="inventory-table">
        <table>
          <thead>
            <tr>
              <th style={{ minWidth: '120px' }}>{t('scheduler.doctor')}</th>
              {weekDays.map((d, i) => (
                <th key={i} style={{ textAlign: 'center', minWidth: '100px', background: holidayDates.has(toISO(d)) ? '#ebf8ff' : undefined }}>
                  <div>{t(`scheduler.${WEEKDAY_KEYS[i]}Short`)}</div>
                  <div style={{ fontWeight: '400', fontSize: '0.8rem', color: '#718096' }}>{fmtDate(d)}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {vets.length === 0 ? (
              <tr><td colSpan="8" style={{ textAlign: 'center', padding: '2rem', color: '#718096' }}>{t('scheduler.noDoctors')}</td></tr>
            ) : (
              vets.map((vet) => (
                <tr key={vet.id}>
                  <td><strong>{vet.first_name} {vet.last_name}</strong></td>
                  {weekDays.map((day, i) => {
                    const { type, lines } = getCellContent(vet, day)
                    return (
                      <td key={i} style={{ textAlign: 'center', fontSize: '0.75rem', padding: '0.4rem 0.3rem', verticalAlign: 'middle', ...cellStyle(type) }}>
                        {lines.map((l, li) => <div key={li}>{l}</div>)}
                      </td>
                    )
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem', marginTop: '0.75rem', fontSize: '0.8rem', color: '#718096', flexWrap: 'wrap' }}>
        <span><span style={{ display: 'inline-block', width: '10px', height: '10px', background: '#f0fff4', border: '1px solid #c6f6d5', marginRight: '4px' }} />{t('scheduler.onDuty')}</span>
        <span><span style={{ display: 'inline-block', width: '10px', height: '10px', background: '#f7fafc', border: '1px solid #e2e8f0', marginRight: '4px' }} />{t('scheduler.scheduledNotPlanned')}</span>
        <span><span style={{ display: 'inline-block', width: '10px', height: '10px', background: '#fff5f5', border: '1px solid #fed7d7', marginRight: '4px' }} />{t('scheduler.dayOff')}</span>
        <span><span style={{ display: 'inline-block', width: '10px', height: '10px', background: '#ebf8ff', border: '1px solid #bee3f8', marginRight: '4px' }} />{t('scheduler.holiday')}</span>
      </div>
    </div>
  )
}

// ─── sub-tab: Doctor Hours ─────────────────────────────────────────────────────

const DoctorHoursTab = ({ vets, workingHours, onRefresh }) => {
  const { t } = useTranslation()
  const [selectedVetId, setSelectedVetId] = useState(vets[0]?.id || '')
  const [schedule, setSchedule] = useState({}) // weekday(0-6) → { active, start, end, existingId }
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  const buildSchedule = useCallback((vetId) => {
    const result = {}
    for (let d = 0; d <= 6; d++) {
      const wh = workingHours.find((w) => w.vet === vetId && w.weekday === d)
      result[d] = {
        active: !!wh?.is_active,
        start: wh ? wh.start_time.slice(0, 5) : '08:00',
        end: wh ? wh.end_time.slice(0, 5) : '16:00',
        existingId: wh?.id || null,
      }
    }
    return result
  }, [workingHours])

  useEffect(() => {
    if (selectedVetId) setSchedule(buildSchedule(Number(selectedVetId)))
  }, [selectedVetId, workingHours, buildSchedule])

  const toggle = (d) =>
    setSchedule((prev) => ({ ...prev, [d]: { ...prev[d], active: !prev[d].active } }))

  const setTime = (d, field, val) =>
    setSchedule((prev) => ({ ...prev, [d]: { ...prev[d], [field]: val } }))

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSuccess(false)
    try {
      const ops = Object.entries(schedule).map(async ([day, cfg]) => {
        const weekday = Number(day)
        if (cfg.active) {
          const payload = { vet: Number(selectedVetId), weekday, start_time: cfg.start, end_time: cfg.end, is_active: true }
          if (cfg.existingId) {
            await schedulerAPI.updateWorkingHours(cfg.existingId, payload)
          } else {
            await schedulerAPI.createWorkingHours(payload)
          }
        } else if (cfg.existingId) {
          await schedulerAPI.deleteWorkingHours(cfg.existingId)
        }
      })
      await Promise.all(ops)
      setSuccess(true)
      onRefresh()
      setTimeout(() => setSuccess(false), 2500)
    } catch (err) {
      const data = err.response?.data
      const src = data?.details || data
      setError(src ? Object.values(src).flat().join(' ') : t('scheduler.saveError'))
    } finally {
      setSaving(false)
    }
  }

  const inputStyle = { border: '1px solid #cbd5e0', borderRadius: '4px', padding: '0.25rem 0.4rem', fontSize: '0.85rem' }

  return (
    <div>
      <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <label style={{ fontWeight: '500' }}>{t('scheduler.selectDoctor')}:</label>
        <select value={selectedVetId} onChange={(e) => setSelectedVetId(e.target.value)} style={{ ...inputStyle, minWidth: '180px' }}>
          {vets.map((v) => (
            <option key={v.id} value={v.id}>{v.first_name} {v.last_name}</option>
          ))}
        </select>
      </div>

      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{t('scheduler.saved')}</div>}

      <div className="inventory-table">
        <table>
          <thead>
            <tr>
              <th>{t('scheduler.day')}</th>
              <th>{t('scheduler.working')}</th>
              <th>{t('scheduler.startTime')}</th>
              <th>{t('scheduler.endTime')}</th>
            </tr>
          </thead>
          <tbody>
            {WEEKDAY_KEYS.map((key, d) => (
              <tr key={d} style={{ opacity: schedule[d]?.active ? 1 : 0.5 }}>
                <td style={{ fontWeight: '500', width: '120px' }}>{t(`scheduler.${key}`)}</td>
                <td style={{ width: '80px' }}>
                  <input type="checkbox" checked={!!schedule[d]?.active} onChange={() => toggle(d)} />
                </td>
                <td>
                  <input type="time" style={inputStyle} value={schedule[d]?.start || '08:00'}
                    disabled={!schedule[d]?.active}
                    onChange={(e) => setTime(d, 'start', e.target.value)} />
                </td>
                <td>
                  <input type="time" style={inputStyle} value={schedule[d]?.end || '16:00'}
                    disabled={!schedule[d]?.active}
                    onChange={(e) => setTime(d, 'end', e.target.value)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: '1rem' }}>
        <button className="btn-primary" disabled={saving || !selectedVetId} onClick={handleSave}>
          {saving ? t('common.saving') : t('common.save')}
        </button>
      </div>
    </div>
  )
}

// ─── sub-tab: Leaves & Day-offs ────────────────────────────────────────────────

const EMPTY_EXC = { vet: '', date: '', is_day_off: true, start_time: '', end_time: '', note: '' }

const LeavesTab = ({ vets, exceptions, onRefresh }) => {
  const { t } = useTranslation()
  const [form, setForm] = useState(EMPTY_EXC)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [filterVet, setFilterVet] = useState('')

  const displayed = exceptions
    .filter((e) => !filterVet || e.vet === Number(filterVet))
    .sort((a, b) => a.date.localeCompare(b.date))

  const handleAdd = async () => {
    if (!form.vet || !form.date) { setError(t('scheduler.vetDateRequired')); return }
    setSaving(true); setError(null)
    try {
      const payload = {
        vet: Number(form.vet),
        date: form.date,
        is_day_off: form.is_day_off,
        start_time: form.is_day_off ? null : (form.start_time || null),
        end_time: form.is_day_off ? null : (form.end_time || null),
        note: form.note,
      }
      await schedulerAPI.createException(payload)
      setForm(EMPTY_EXC)
      setShowForm(false)
      onRefresh()
    } catch (err) {
      const data = err.response?.data
      const src = data?.details || data
      setError(src ? Object.values(src).flat().join(' ') : t('scheduler.saveError'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm(t('scheduler.deleteConfirm'))) return
    setDeletingId(id)
    try {
      await schedulerAPI.deleteException(id)
      onRefresh()
    } finally {
      setDeletingId(null)
    }
  }

  const inputStyle = { border: '1px solid #cbd5e0', borderRadius: '4px', padding: '0.3rem 0.5rem', fontSize: '0.85rem' }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
        <select value={filterVet} onChange={(e) => setFilterVet(e.target.value)} style={{ ...inputStyle, minWidth: '160px' }}>
          <option value="">{t('scheduler.allDoctors')}</option>
          {vets.map((v) => <option key={v.id} value={v.id}>{v.first_name} {v.last_name}</option>)}
        </select>
        <button className="btn-primary" onClick={() => { setShowForm(true); setError(null) }} style={{ marginLeft: 'auto' }}>
          {t('scheduler.addLeave')}
        </button>
      </div>

      {showForm && (
        <div style={{ background: '#f7fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '1rem', marginBottom: '1rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: '500', display: 'block', marginBottom: '2px' }}>{t('scheduler.doctor')} *</label>
              <select value={form.vet} onChange={(e) => setForm((p) => ({ ...p, vet: e.target.value }))} style={{ ...inputStyle, width: '100%' }}>
                <option value="">—</option>
                {vets.map((v) => <option key={v.id} value={v.id}>{v.first_name} {v.last_name}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: '500', display: 'block', marginBottom: '2px' }}>{t('scheduler.date')} *</label>
              <input type="date" value={form.date} onChange={(e) => setForm((p) => ({ ...p, date: e.target.value }))} style={{ ...inputStyle, width: '100%' }} />
            </div>
            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: '500', display: 'block', marginBottom: '2px' }}>{t('scheduler.type')}</label>
              <select value={form.is_day_off ? 'off' : 'custom'} onChange={(e) => setForm((p) => ({ ...p, is_day_off: e.target.value === 'off' }))} style={{ ...inputStyle, width: '100%' }}>
                <option value="off">{t('scheduler.dayOff')}</option>
                <option value="custom">{t('scheduler.customHours')}</option>
              </select>
            </div>
            {!form.is_day_off && (
              <>
                <div>
                  <label style={{ fontSize: '0.8rem', fontWeight: '500', display: 'block', marginBottom: '2px' }}>{t('scheduler.startTime')}</label>
                  <input type="time" value={form.start_time} onChange={(e) => setForm((p) => ({ ...p, start_time: e.target.value }))} style={{ ...inputStyle, width: '100%' }} />
                </div>
                <div>
                  <label style={{ fontSize: '0.8rem', fontWeight: '500', display: 'block', marginBottom: '2px' }}>{t('scheduler.endTime')}</label>
                  <input type="time" value={form.end_time} onChange={(e) => setForm((p) => ({ ...p, end_time: e.target.value }))} style={{ ...inputStyle, width: '100%' }} />
                </div>
              </>
            )}
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: '500', display: 'block', marginBottom: '2px' }}>{t('scheduler.note')}</label>
              <input type="text" value={form.note} onChange={(e) => setForm((p) => ({ ...p, note: e.target.value }))} style={{ ...inputStyle, width: '100%' }} placeholder={t('scheduler.notePlaceholder')} />
            </div>
          </div>
          {error && <div className="error-message" style={{ marginBottom: '0.5rem' }}>{error}</div>}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn-primary" disabled={saving} onClick={handleAdd}>{saving ? t('common.saving') : t('common.save')}</button>
            <button className="btn-secondary" onClick={() => { setShowForm(false); setError(null) }}>{t('common.cancel')}</button>
          </div>
        </div>
      )}

      <div className="inventory-table">
        <table>
          <thead>
            <tr>
              <th>{t('scheduler.doctor')}</th>
              <th>{t('scheduler.date')}</th>
              <th>{t('scheduler.type')}</th>
              <th>{t('scheduler.hours')}</th>
              <th>{t('scheduler.note')}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {displayed.length === 0 ? (
              <tr><td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: '#718096' }}>{t('scheduler.noLeaves')}</td></tr>
            ) : displayed.map((exc) => {
              const vet = vets.find((v) => v.id === exc.vet)
              return (
                <tr key={exc.id}>
                  <td>{exc.vet_name || (vet ? `${vet.first_name} ${vet.last_name}` : exc.vet)}</td>
                  <td>{exc.date}</td>
                  <td>
                    {exc.is_day_off
                      ? <span className="status-badge" style={{ background: '#fff5f5', color: '#c53030' }}>{t('scheduler.dayOff')}</span>
                      : <span className="status-badge" style={{ background: '#fffff0', color: '#744210' }}>{t('scheduler.customHours')}</span>}
                  </td>
                  <td style={{ fontSize: '0.85rem', color: '#718096' }}>
                    {!exc.is_day_off && exc.start_time ? `${formatTime(exc.start_time)}–${formatTime(exc.end_time)}` : '—'}
                  </td>
                  <td style={{ fontSize: '0.85rem', color: '#718096' }}>{exc.note || '—'}</td>
                  <td>
                    <button className="btn-link" style={{ color: '#e53e3e', fontSize: '0.85rem' }}
                      disabled={deletingId === exc.id} onClick={() => handleDelete(exc.id)}>
                      {t('common.delete')}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── sub-tab: Clinic Holidays ──────────────────────────────────────────────────

const HolidaysTab = ({ holidays, onRefresh }) => {
  const { t } = useTranslation()
  const [form, setForm] = useState({ date: '', reason: '' })
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [deletingId, setDeletingId] = useState(null)

  const handleAdd = async () => {
    if (!form.date) { setError(t('scheduler.dateRequired')); return }
    setSaving(true); setError(null)
    try {
      await schedulerAPI.createHoliday({ date: form.date, reason: form.reason })
      setForm({ date: '', reason: '' })
      setShowForm(false)
      onRefresh()
    } catch (err) {
      const data = err.response?.data
      const src = data?.details || data
      setError(src ? Object.values(src).flat().join(' ') : t('scheduler.saveError'))
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (holiday) => {
    try {
      await schedulerAPI.updateHoliday(holiday.id, { is_active: !holiday.is_active })
      onRefresh()
    } catch { /* ignore */ }
  }

  const handleDelete = async (id) => {
    if (!window.confirm(t('scheduler.deleteConfirm'))) return
    setDeletingId(id)
    try {
      await schedulerAPI.deleteHoliday(id)
      onRefresh()
    } finally {
      setDeletingId(null)
    }
  }

  const inputStyle = { border: '1px solid #cbd5e0', borderRadius: '4px', padding: '0.3rem 0.5rem', fontSize: '0.85rem' }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
        <button className="btn-primary" onClick={() => { setShowForm(true); setError(null) }}>
          {t('scheduler.addHoliday')}
        </button>
      </div>

      {showForm && (
        <div style={{ background: '#f7fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '1rem', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: '500', display: 'block', marginBottom: '2px' }}>{t('scheduler.date')} *</label>
              <input type="date" value={form.date} onChange={(e) => setForm((p) => ({ ...p, date: e.target.value }))} style={inputStyle} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '0.8rem', fontWeight: '500', display: 'block', marginBottom: '2px' }}>{t('scheduler.reason')}</label>
              <input type="text" value={form.reason} onChange={(e) => setForm((p) => ({ ...p, reason: e.target.value }))} style={{ ...inputStyle, width: '100%' }} placeholder={t('scheduler.reasonPlaceholder')} />
            </div>
          </div>
          {error && <div className="error-message" style={{ marginBottom: '0.5rem' }}>{error}</div>}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn-primary" disabled={saving} onClick={handleAdd}>{saving ? t('common.saving') : t('common.save')}</button>
            <button className="btn-secondary" onClick={() => { setShowForm(false); setError(null) }}>{t('common.cancel')}</button>
          </div>
        </div>
      )}

      <div className="inventory-table">
        <table>
          <thead>
            <tr>
              <th>{t('scheduler.date')}</th>
              <th>{t('scheduler.reason')}</th>
              <th>{t('scheduler.status')}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {holidays.length === 0 ? (
              <tr><td colSpan="4" style={{ textAlign: 'center', padding: '2rem', color: '#718096' }}>{t('scheduler.noHolidays')}</td></tr>
            ) : holidays.map((h) => (
              <tr key={h.id} style={{ opacity: h.is_active ? 1 : 0.5 }}>
                <td style={{ fontWeight: '500' }}>{h.date}</td>
                <td style={{ color: '#718096' }}>{h.reason || '—'}</td>
                <td>
                  <button className="btn-link" style={{ fontSize: '0.85rem' }} onClick={() => handleToggle(h)}>
                    {h.is_active
                      ? <span className="status-badge" style={{ background: '#ebf8ff', color: '#2b6cb0' }}>{t('scheduler.active')}</span>
                      : <span className="status-badge" style={{ background: '#f7fafc', color: '#718096' }}>{t('scheduler.inactive')}</span>}
                  </button>
                </td>
                <td>
                  <button className="btn-link" style={{ color: '#e53e3e', fontSize: '0.85rem' }}
                    disabled={deletingId === h.id} onClick={() => handleDelete(h.id)}>
                    {t('common.delete')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── main component ────────────────────────────────────────────────────────────

const TABS = ['weekView', 'doctorHours', 'leaves', 'holidays', 'planner']

const SchedulerTab = () => {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('weekView')
  const [vets, setVets] = useState([])
  const [workingHours, setWorkingHours] = useState([])
  const [exceptions, setExceptions] = useState([])
  const [holidays, setHolidays] = useState([])
  const [initialAssignments, setInitialAssignments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // Fetch assignments for current week as initial data for the WeekView
      const today = new Date()
      const weekStart = getWeekStart(today)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekEnd.getDate() + 6)

      const [vetsRes, whRes, excRes, holRes, assignRes] = await Promise.all([
        vetsAPI.list(),
        schedulerAPI.listWorkingHours(),
        schedulerAPI.listExceptions(),
        schedulerAPI.listHolidays(),
        schedulerAPI.listAssignments({ from: toISO(weekStart), to: toISO(weekEnd) }),
      ])
      setVets(vetsRes.data.results || vetsRes.data)
      setWorkingHours(whRes.data.results || whRes.data)
      setExceptions(excRes.data.results || excRes.data)
      setHolidays(holRes.data.results || holRes.data)
      setInitialAssignments(assignRes.data.results || assignRes.data)
    } catch {
      setError(t('scheduler.loadError'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => { loadData() }, [loadData])

  return (
    <div className="tab-container">
      <div className="tab-header">
      </div>

      <div className="tab-content-wrapper">
        <div className="sub-tabs" style={{ display: 'flex', gap: '0.25rem', borderBottom: '2px solid #e2e8f0', marginBottom: '1.5rem' }}>
          {TABS.map((tab) => (
            <button key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: '0.5rem 1rem',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                fontSize: '0.9rem',
                color: activeTab === tab ? '#3182ce' : '#718096',
                borderBottom: activeTab === tab ? '2px solid #3182ce' : '2px solid transparent',
                marginBottom: '-2px',
                fontWeight: activeTab === tab ? '600' : '400',
              }}>
              {t(`scheduler.tab_${tab}`)}
            </button>
          ))}
        </div>

        {loading && <div className="loading-message">{t('common.loading')}</div>}
        {error && <div className="error-message">{error}</div>}

        {!loading && !error && (
          <>
            {activeTab === 'weekView' && (
              <WeekView vets={vets} workingHours={workingHours} exceptions={exceptions} holidays={holidays} assignments={initialAssignments} />
            )}
            {activeTab === 'doctorHours' && (
              <DoctorHoursTab vets={vets} workingHours={workingHours} onRefresh={loadData} />
            )}
            {activeTab === 'leaves' && (
              <LeavesTab vets={vets} exceptions={exceptions} onRefresh={loadData} />
            )}
            {activeTab === 'holidays' && (
              <HolidaysTab holidays={holidays} onRefresh={loadData} />
            )}
            {activeTab === 'planner' && (
              <SchedulePlannerTab />
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default SchedulerTab
