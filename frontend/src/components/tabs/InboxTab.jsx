import React, { useState, useEffect, useCallback } from 'react'
import { inboxAPI, vetsAPI } from '../../services/api'
import './Tabs.css'

const TASK_TYPE_LABELS = {
  phone_callback: 'Oddzwonienie',
  sign_document: 'Do podpisu',
  check_result: 'Sprawdź wynik',
  other: 'Inne',
}

const STATUS_LABELS = {
  open: 'Otwarte',
  in_progress: 'W toku',
  closed: 'Zamknięte',
}

const STATUS_COLORS = {
  open: { bg: '#fff7ed', border: '#fed7aa', text: '#c2410c', dot: '#f97316' },
  in_progress: { bg: '#eff6ff', border: '#bfdbfe', text: '#1d4ed8', dot: '#3b82f6' },
  closed: { bg: '#f9fafb', border: '#e5e7eb', text: '#6b7280', dot: '#9ca3af' },
}

const REFRESH_MS = 30000

const NewTaskModal = ({ isOpen, onClose, onSuccess, vets }) => {
  const [form, setForm] = useState({ vet: '', task_type: 'other', patient_name: '', note: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (isOpen) setForm({ vet: '', task_type: 'other', patient_name: '', note: '' })
    setError(null)
  }, [isOpen])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.vet || !form.note.trim()) { setError('Wybierz lekarza i wpisz treść zadania.'); return }
    setLoading(true)
    try {
      await inboxAPI.create(form)
      onSuccess()
    } catch (err) {
      setError(err.response?.data?.detail || 'Błąd zapisu.')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '460px' }}>
        <div className="modal-header">
          <h2>Nowe zadanie</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}
          <div className="form-group">
            <label>Lekarz</label>
            <select value={form.vet} onChange={e => setForm(p => ({ ...p, vet: e.target.value }))} required>
              <option value="">Wybierz lekarza...</option>
              {vets.map(v => (
                <option key={v.id} value={v.id}>{v.first_name} {v.last_name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Typ zadania</label>
            <select value={form.task_type} onChange={e => setForm(p => ({ ...p, task_type: e.target.value }))}>
              {Object.entries(TASK_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Pacjent / klient <span style={{ fontWeight: 400, color: '#a0aec0' }}>(opcjonalne)</span></label>
            <input
              type="text"
              value={form.patient_name}
              onChange={e => setForm(p => ({ ...p, patient_name: e.target.value }))}
              placeholder="np. Jan Kowalski / Reks"
            />
          </div>
          <div className="form-group">
            <label>Treść zadania</label>
            <textarea
              value={form.note}
              onChange={e => setForm(p => ({ ...p, note: e.target.value }))}
              rows="3"
              placeholder="Opisz zadanie..."
              required
            />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Anuluj</button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Zapisuję...' : 'Utwórz zadanie'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const CloseCommentModal = ({ isOpen, onClose, onConfirm }) => {
  const [comment, setComment] = useState('')
  useEffect(() => { if (isOpen) setComment('') }, [isOpen])
  if (!isOpen) return null
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '380px' }}>
        <div className="modal-header">
          <h2>Zamknij zadanie</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-form">
          <div className="form-group">
            <label>Komentarz <span style={{ fontWeight: 400, color: '#a0aec0' }}>(opcjonalny)</span></label>
            <textarea value={comment} onChange={e => setComment(e.target.value)} rows="3" placeholder="Co zostało zrobione?" />
          </div>
          <div className="modal-actions">
            <button className="btn-secondary" onClick={onClose}>Anuluj</button>
            <button className="btn-primary" onClick={() => onConfirm(comment)}>Zamknij zadanie</button>
          </div>
        </div>
      </div>
    </div>
  )
}

const TaskCard = ({ task, userRole, onStatusChange, onDelete }) => {
  const [closing, setClosing] = useState(false)
  const [actioning, setActioning] = useState(false)
  const colors = STATUS_COLORS[task.status]
  const isReceptionist = userRole === 'receptionist' || userRole === 'admin'
  const isClosed = task.status === 'closed'

  const formatDate = (ds) => {
    if (!ds) return ''
    return new Date(ds).toLocaleString('pl-PL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  const handleStatusClick = async (newStatus) => {
    if (newStatus === 'closed') { setClosing(true); return }
    setActioning(true)
    try { await onStatusChange(task.id, newStatus, '') } finally { setActioning(false) }
  }

  const handleCloseConfirm = async (comment) => {
    setClosing(false)
    setActioning(true)
    try { await onStatusChange(task.id, 'closed', comment) } finally { setActioning(false) }
  }

  return (
    <>
      <div style={{
        background: isClosed ? '#f9fafb' : 'white',
        border: `1px solid ${colors.border}`,
        borderLeft: `4px solid ${colors.dot}`,
        borderRadius: '10px',
        padding: '0.875rem 1rem',
        marginBottom: '0.6rem',
        opacity: actioning ? 0.6 : 1,
        transition: 'opacity 0.15s',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.3rem' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: '700', background: colors.bg, color: colors.text, border: `1px solid ${colors.border}`, borderRadius: '999px', padding: '0.1rem 0.5rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                {STATUS_LABELS[task.status]}
              </span>
              <span style={{ fontSize: '0.78rem', fontWeight: '600', color: '#6b7280', background: '#f3f4f6', borderRadius: '999px', padding: '0.1rem 0.5rem' }}>
                {TASK_TYPE_LABELS[task.task_type]}
              </span>
              {task.patient_name && (
                <span style={{ fontSize: '0.82rem', color: '#374151', fontWeight: '500' }}>
                  🐾 {task.patient_name}
                </span>
              )}
            </div>
            <div style={{ fontSize: '0.92rem', color: '#1f2937', marginBottom: '0.3rem', lineHeight: 1.4 }}>
              {task.note}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
              {task.created_by_name && `Dodane przez: ${task.created_by_name} · `}{formatDate(task.created_at)}
            </div>
            {isClosed && (
              <div style={{ marginTop: '0.3rem', fontSize: '0.78rem', color: '#6b7280' }}>
                Zamknięte przez: {task.closed_by_name} · {formatDate(task.closed_at)}
                {task.close_comment && <div style={{ marginTop: '0.15rem', fontStyle: 'italic' }}>"{task.close_comment}"</div>}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', flexShrink: 0 }}>
            {!isClosed && (
              <>
                {task.status === 'open' && (
                  <button onClick={() => handleStatusClick('in_progress')} disabled={actioning}
                    style={{ padding: '0.3rem 0.6rem', border: '1px solid #bfdbfe', borderRadius: '6px', background: '#eff6ff', color: '#1d4ed8', fontSize: '0.8rem', fontWeight: '600', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                    Przyjmij
                  </button>
                )}
                {task.status === 'in_progress' && (
                  <button onClick={() => handleStatusClick('closed')} disabled={actioning}
                    style={{ padding: '0.3rem 0.6rem', border: '1px solid #bbf7d0', borderRadius: '6px', background: '#f0fdf4', color: '#15803d', fontSize: '0.8rem', fontWeight: '600', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                    Zamknij
                  </button>
                )}
              </>
            )}
            {isReceptionist && (
              <button onClick={() => onDelete(task.id)} disabled={actioning}
                style={{ padding: '0.3rem 0.5rem', border: '1px solid #fecaca', borderRadius: '6px', background: '#fff5f5', color: '#dc2626', fontSize: '0.78rem', cursor: 'pointer' }}>
                Usuń
              </button>
            )}
          </div>
        </div>
      </div>
      <CloseCommentModal
        isOpen={closing}
        onClose={() => setClosing(false)}
        onConfirm={handleCloseConfirm}
      />
    </>
  )
}

const InboxTab = ({ userRole, currentUserId }) => {
  const [tasks, setTasks] = useState([])
  const [vets, setVets] = useState([])
  const [loading, setLoading] = useState(true)
  const [isNewTaskOpen, setIsNewTaskOpen] = useState(false)
  const [showClosed, setShowClosed] = useState({})
  const isReceptionist = userRole === 'receptionist' || userRole === 'admin'

  const fetchTasks = useCallback(async () => {
    try {
      const res = await inboxAPI.list()
      setTasks(res.data.results || res.data || [])
    } catch {
      setTasks([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTasks()
    if (isReceptionist) {
      vetsAPI.list().then(r => setVets(r.data.results || r.data || [])).catch(() => {})
    }
    const interval = setInterval(fetchTasks, REFRESH_MS)
    return () => clearInterval(interval)
  }, [fetchTasks, isReceptionist])

  const handleStatusChange = async (id, status, closeComment) => {
    await inboxAPI.setStatus(id, status, closeComment)
    await fetchTasks()
  }

  const handleDelete = async (id) => {
    await inboxAPI.delete(id)
    await fetchTasks()
  }

  const toggleClosed = (vetId) => setShowClosed(p => ({ ...p, [vetId]: !p[vetId] }))

  if (loading) return <div className="tab-container"><div className="loading-message">Ładowanie...</div></div>

  // Doctor view — own tasks only
  if (!isReceptionist) {
    const open = tasks.filter(t => t.status === 'open')
    const inProgress = tasks.filter(t => t.status === 'in_progress')
    const closed = tasks.filter(t => t.status === 'closed')
    const showClosedDoctor = showClosed['doctor'] || false

    return (
      <div className="tab-container">
        <div className="tab-header" style={{ justifyContent: 'flex-end' }}>
          <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>
            {open.length + inProgress.length} aktywnych zadań
          </span>
        </div>
        <div className="tab-content-wrapper">
          {tasks.length === 0 && (
            <div style={{ textAlign: 'center', padding: '4rem 2rem', color: '#9ca3af' }}>
              Brak zadań w skrzynce
            </div>
          )}
          {[...open, ...inProgress].map(task => (
            <TaskCard key={task.id} task={task} userRole={userRole} onStatusChange={handleStatusChange} onDelete={handleDelete} />
          ))}
          {closed.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <button
                onClick={() => toggleClosed('doctor')}
                style={{ background: 'none', border: 'none', color: '#6b7280', fontSize: '0.85rem', fontWeight: '600', cursor: 'pointer', padding: '0.25rem 0', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
              >
                {showClosedDoctor ? '▾' : '▸'} Zamknięte ({closed.length})
              </button>
              {showClosedDoctor && closed.map(task => (
                <TaskCard key={task.id} task={task} userRole={userRole} onStatusChange={handleStatusChange} onDelete={handleDelete} />
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // Receptionist/admin view — grouped by vet
  const vetIds = [...new Set(tasks.map(t => t.vet))]
  const vetMap = {}
  vets.forEach(v => { vetMap[v.id] = v })
  tasks.forEach(t => { if (!vetMap[t.vet]) vetMap[t.vet] = { id: t.vet, first_name: '', last_name: t.vet_name || `Lekarz #${t.vet}` } })

  const uniqueVetIds = [...new Set(tasks.map(t => t.vet))]

  return (
    <div className="tab-container">
      <div className="tab-header">
        <button className="btn-primary" onClick={() => setIsNewTaskOpen(true)}>
          + Nowe zadanie
        </button>
      </div>
      <div className="tab-content-wrapper">
        {uniqueVetIds.length === 0 && (
          <div style={{ textAlign: 'center', padding: '4rem 2rem', color: '#9ca3af' }}>
            Brak zadań. Kliknij „+ Nowe zadanie" aby dodać.
          </div>
        )}
        {uniqueVetIds.map(vetId => {
          const vetTasks = tasks.filter(t => t.vet === vetId)
          const vet = vetMap[vetId]
          const vetName = vet ? `${vet.first_name} ${vet.last_name}`.trim() || vet.last_name : `Lekarz #${vetId}`
          const active = vetTasks.filter(t => t.status !== 'closed')
          const closed = vetTasks.filter(t => t.status === 'closed')
          const showClosedVet = showClosed[vetId] || false

          return (
            <div key={vetId} style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: active.length > 0 ? '#f97316' : '#d1d5db', flexShrink: 0 }} />
                <span style={{ fontWeight: '700', fontSize: '0.9rem', color: '#1f2937' }}>{vetName}</span>
                <span style={{ fontSize: '0.78rem', color: '#9ca3af' }}>({active.length} aktywnych)</span>
              </div>
              {active.length === 0 && (
                <div style={{ fontSize: '0.85rem', color: '#9ca3af', padding: '0.5rem 0.75rem', background: '#f9fafb', borderRadius: '8px', marginBottom: '0.4rem' }}>
                  Brak aktywnych zadań
                </div>
              )}
              {active.map(task => (
                <TaskCard key={task.id} task={task} userRole={userRole} onStatusChange={handleStatusChange} onDelete={handleDelete} />
              ))}
              {closed.length > 0 && (
                <div>
                  <button
                    onClick={() => toggleClosed(vetId)}
                    style={{ background: 'none', border: 'none', color: '#6b7280', fontSize: '0.8rem', fontWeight: '600', cursor: 'pointer', padding: '0.2rem 0', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                  >
                    {showClosedVet ? '▾' : '▸'} Zamknięte ({closed.length})
                  </button>
                  {showClosedVet && closed.map(task => (
                    <TaskCard key={task.id} task={task} userRole={userRole} onStatusChange={handleStatusChange} onDelete={handleDelete} />
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
      <NewTaskModal
        isOpen={isNewTaskOpen}
        onClose={() => setIsNewTaskOpen(false)}
        onSuccess={() => { setIsNewTaskOpen(false); fetchTasks() }}
        vets={vets}
      />
    </div>
  )
}

export default InboxTab
