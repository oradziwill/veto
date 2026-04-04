import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { patientHistoryAPI, patientAISummaryAPI, prescriptionsAPI } from '../../services/api'
import { translateSpecies } from '../../utils/species'
import './Modal.css'

const TABS = ['overview', 'history', 'prescriptions']

/**
 * Splits a structured visit note into { services, medications, cleanNote }.
 * Sections written by StartVisitModal:
 *   "Usługi:\n- Service (price PLN)\n..."
 *   "Leki:\n- Med xQty unit\n..."
 * Everything else is returned as cleanNote.
 */
function parseNote(note) {
  if (!note) return { services: [], medications: [], cleanNote: '' }

  const paragraphs = note.split(/\n\n+/)
  const services = []
  const medications = []
  const rest = []

  for (const para of paragraphs) {
    const lines = para.split('\n')
    const header = lines[0].trim()
    if (header === 'Usługi:') {
      lines.slice(1).forEach(l => { if (l.trim()) services.push(l.replace(/^- /, '').trim()) })
    } else if (header === 'Leki:') {
      lines.slice(1).forEach(l => { if (l.trim()) medications.push(l.replace(/^- /, '').trim()) })
    } else {
      rest.push(para)
    }
  }

  return { services, medications, cleanNote: rest.join('\n\n') }
}

const PatientDetailsModal = ({ isOpen, onClose, patient, userRole = null }) => {
  const { t, i18n } = useTranslation()
  const [activeTab, setActiveTab] = useState('overview')

  // History
  const [history, setHistory] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [historyError, setHistoryError] = useState(null)

  // AI summary
  const [aiSummary, setAiSummary] = useState(null)
  const [loadingAISummary, setLoadingAISummary] = useState(false)
  const [aiSummaryError, setAiSummaryError] = useState(null)
  const [, setAiSummaryCached] = useState(false)

  // Prescriptions
  const [prescriptions, setPrescriptions] = useState([])
  const [loadingPrescriptions, setLoadingPrescriptions] = useState(false)
  const [prescriptionsError, setPrescriptionsError] = useState(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [form, setForm] = useState({ drug_name: '', dosage: '', duration_days: '', notes: '' })

  const hasFetchedRef = useRef(false)
  const hasFetchedAISummaryRef = useRef(false)
  const hasFetchedRxRef = useRef(false)
  const currentPatientIdRef = useRef(null)

  useEffect(() => {
    if (!isOpen) {
      setHistory([])
      setHistoryError(null)
      setLoadingHistory(false)
      setAiSummary(null)
      setAiSummaryError(null)
      setLoadingAISummary(false)
      setAiSummaryCached(false)
      setPrescriptions([])
      setPrescriptionsError(null)
      setShowAddForm(false)
      setSaveError(null)
      setForm({ drug_name: '', dosage: '', duration_days: '', notes: '' })
      hasFetchedRef.current = false
      hasFetchedAISummaryRef.current = false
      hasFetchedRxRef.current = false
      currentPatientIdRef.current = null
      setActiveTab('overview')
      return
    }

    if (!patient?.id) return

    if (currentPatientIdRef.current !== patient.id) {
      hasFetchedRef.current = false
      hasFetchedAISummaryRef.current = false
      hasFetchedRxRef.current = false
      currentPatientIdRef.current = patient.id
    }

    if (patient.ai_summary && !aiSummary) {
      setAiSummary(patient.ai_summary)
      setAiSummaryCached(true)
    }

    if (!hasFetchedRef.current) {
      hasFetchedRef.current = true
      setLoadingHistory(true)
      setHistoryError(null)
      patientHistoryAPI.list(patient.id)
        .then((res) => setHistory(res.data || []))
        .catch(() => {
          setHistoryError(t('patientDetails.loadHistoryError'))
          hasFetchedRef.current = false
        })
        .finally(() => setLoadingHistory(false))
    }

    if (!hasFetchedAISummaryRef.current) {
      hasFetchedAISummaryRef.current = true
      if (!patient.ai_summary) setLoadingAISummary(true)
      setAiSummaryError(null)
      patientAISummaryAPI.get(patient.id)
        .then((res) => {
          setAiSummary(res.data.summary || null)
          setAiSummaryCached(res.data.cached || false)
        })
        .catch((err) => {
          setAiSummaryError(err.response?.data?.error || t('patientDetails.aiSummaryError'))
          hasFetchedAISummaryRef.current = false
        })
        .finally(() => setLoadingAISummary(false))
    }

    if (!hasFetchedRxRef.current) {
      hasFetchedRxRef.current = true
      setLoadingPrescriptions(true)
      prescriptionsAPI.list(patient.id)
        .then((res) => setPrescriptions(res.data.results || res.data || []))
        .catch(() => {
          setPrescriptionsError(t('patientDetails.prescriptions.loadError'))
          hasFetchedRxRef.current = false
        })
        .finally(() => setLoadingPrescriptions(false))
    }
  }, [isOpen, patient?.id])

  const locale = i18n.language === 'pl' ? 'pl-PL' : 'en-US'

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleDateString(locale, {
      year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  const formatDateOnly = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleDateString(locale, {
      year: 'numeric', month: 'long', day: 'numeric',
    })
  }

  const calculateAge = (birthDate) => {
    if (!birthDate) return t('common.unknown')
    const today = new Date()
    const birth = new Date(birthDate)
    let years = today.getFullYear() - birth.getFullYear()
    let months = today.getMonth() - birth.getMonth()
    if (months < 0) { years--; months += 12 }
    if (years > 0) {
      const y = years === 1 ? t('patients.year') : t('patients.years')
      const m = months > 0 ? (months === 1 ? t('patients.month') : t('patients.months')) : ''
      return months > 0 ? `${years} ${y}, ${months} ${m}` : `${years} ${y}`
    }
    return months === 1 ? t('patients.month') : `${months} ${t('patients.months')}`
  }

  const handleAddPrescription = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const payload = {
        drug_name: form.drug_name,
        dosage: form.dosage,
        ...(form.duration_days ? { duration_days: Number(form.duration_days) } : {}),
        ...(form.notes ? { notes: form.notes } : {}),
      }
      const res = await prescriptionsAPI.create(patient.id, payload)
      setPrescriptions((prev) => [res.data, ...prev])
      setShowAddForm(false)
      setForm({ drug_name: '', dosage: '', duration_days: '', notes: '' })
    } catch (err) {
      const data = err.response?.data
      const src = data?.details || data
      setSaveError(src ? Object.values(src).flat().join(' ') : t('patientDetails.prescriptions.saveError'))
    } finally {
      setSaving(false)
    }
  }

  const canWrite = userRole === 'doctor' || userRole === 'admin'

  if (!isOpen || !patient) return null

  const inputStyle = { width: '100%', padding: '0.5rem 0.75rem', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '0.9rem', boxSizing: 'border-box' }
  const labelStyle = { display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#718096', marginBottom: '0.25rem' }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '900px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="modal-header">
          <h2>{t('patientDetails.title')}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {/* Tab navigation */}
        <div style={{ display: 'flex', gap: '0.25rem', borderBottom: '2px solid #e2e8f0', padding: '0 1.5rem' }}>
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: '0.6rem 1rem',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                fontSize: '0.9rem',
                fontWeight: activeTab === tab ? '600' : '400',
                color: activeTab === tab ? '#3182ce' : '#718096',
                borderBottom: activeTab === tab ? '2px solid #3182ce' : '2px solid transparent',
                marginBottom: '-2px',
              }}
            >
              {t(`patientDetails.tabs.${tab}`)}
              {tab === 'prescriptions' && prescriptions.length > 0 && (
                <span style={{ marginLeft: '0.4rem', fontSize: '0.75rem', background: '#ebf8ff', color: '#2b6cb0', borderRadius: '10px', padding: '0.1rem 0.45rem', fontWeight: '600' }}>
                  {prescriptions.length}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="modal-form" style={{ padding: '1.5rem' }}>

          {/* ── OVERVIEW TAB ─────────────────────────────────────── */}
          {activeTab === 'overview' && (
            <>
              <div style={{ marginBottom: '2rem' }}>
                <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: '600', color: '#2d3748' }}>{t('patientDetails.patientInfo')}</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                  <div><label style={labelStyle}>{t('patientDetails.name')}</label><div style={{ fontWeight: '500' }}>{patient.name || 'N/A'}</div></div>
                  <div><label style={labelStyle}>{t('patientDetails.species')}</label><div style={{ fontWeight: '500' }}>{patient.species ? translateSpecies(patient.species, t) : 'N/A'}</div></div>
                  <div><label style={labelStyle}>{t('patientDetails.breed')}</label><div style={{ fontWeight: '500' }}>{patient.breed || 'N/A'}</div></div>
                  <div><label style={labelStyle}>{t('patientDetails.sex')}</label><div style={{ fontWeight: '500' }}>{patient.sex || 'N/A'}</div></div>
                  <div><label style={labelStyle}>{t('patientDetails.birthDate')}</label><div style={{ fontWeight: '500' }}>{patient.birth_date ? formatDateOnly(patient.birth_date) : 'N/A'}</div></div>
                  <div><label style={labelStyle}>{t('patientDetails.age')}</label><div style={{ fontWeight: '500' }}>{calculateAge(patient.birth_date)}</div></div>
                  {patient.microchip_no && (
                    <div><label style={labelStyle}>{t('patientDetails.microchipNumber')}</label><div style={{ fontWeight: '500' }}>{patient.microchip_no}</div></div>
                  )}
                </div>
                {patient.allergies && (
                  <div style={{ marginTop: '1rem' }}>
                    <label style={labelStyle}>{t('patientDetails.allergies')}</label>
                    <div style={{ padding: '0.75rem', backgroundColor: '#fff5f5', borderRadius: '6px', border: '1px solid #fed7d7' }}>{patient.allergies}</div>
                  </div>
                )}
                {patient.notes && (
                  <div style={{ marginTop: '1rem' }}>
                    <label style={labelStyle}>{t('patientDetails.notes')}</label>
                    <div style={{ padding: '0.75rem', backgroundColor: '#f7fafc', borderRadius: '6px', border: '1px solid #e2e8f0', whiteSpace: 'pre-wrap' }}>{patient.notes}</div>
                  </div>
                )}
              </div>

              <div style={{ marginBottom: '2rem', paddingTop: '1.5rem', borderTop: '2px solid #e2e8f0' }}>
                <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: '600', color: '#2d3748' }}>{t('patientDetails.aiSummary')}</h3>
                {loadingAISummary && (
                  <div style={{ padding: '1.5rem', textAlign: 'center', color: '#718096', backgroundColor: '#f7fafc', borderRadius: '8px' }}>
                    <div style={{ marginBottom: '0.5rem' }}>{t('patientDetails.generatingSummary')}</div>
                    <div style={{ fontSize: '0.875rem' }}>{t('patientDetails.analyzingHistory')}</div>
                  </div>
                )}
                {aiSummaryError && !loadingAISummary && (
                  <div style={{ padding: '1rem', backgroundColor: '#fff5f5', borderRadius: '8px', border: '1px solid #fed7d7', color: '#c53030' }}>
                    <div style={{ fontWeight: '500', marginBottom: '0.25rem' }}>{t('patientDetails.aiSummaryError')}</div>
                    <div style={{ fontSize: '0.875rem' }}>{aiSummaryError}</div>
                    <button
                      onClick={async () => {
                        try {
                          setLoadingAISummary(true); setAiSummaryError(null)
                          const res = await patientAISummaryAPI.get(patient.id)
                          setAiSummary(res.data.summary || null)
                          setAiSummaryCached(res.data.cached || false)
                          hasFetchedAISummaryRef.current = true
                        } catch (err) {
                          setAiSummaryError(err.response?.data?.error || t('patientDetails.aiSummaryError'))
                          hasFetchedAISummaryRef.current = false
                        } finally { setLoadingAISummary(false) }
                      }}
                      style={{ marginTop: '0.75rem', padding: '0.5rem 1rem', backgroundColor: '#48bb78', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.875rem', fontWeight: '500' }}
                    >
                      {t('common.retry')}
                    </button>
                  </div>
                )}
                {aiSummary && !loadingAISummary && (
                  <div style={{ padding: '1.5rem', backgroundColor: '#f0f9ff', borderRadius: '8px', border: '1px solid #bee3f8', whiteSpace: 'pre-wrap', lineHeight: '1.8', fontSize: '0.9375rem', color: '#2d3748' }}>
                    {aiSummary}
                  </div>
                )}
              </div>

              {patient.owner && (
                <div style={{ paddingTop: '1.5rem', borderTop: '2px solid #e2e8f0' }}>
                  <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: '600', color: '#2d3748' }}>{t('patientDetails.ownerInfo')}</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                    <div><label style={labelStyle}>{t('patientDetails.ownerName')}</label><div style={{ fontWeight: '500' }}>{patient.owner.first_name} {patient.owner.last_name}</div></div>
                    {patient.owner.email && <div><label style={labelStyle}>{t('patientDetails.email')}</label><div style={{ fontWeight: '500' }}>{patient.owner.email}</div></div>}
                    {patient.owner.phone && <div><label style={labelStyle}>{t('patientDetails.phone')}</label><div style={{ fontWeight: '500' }}>{patient.owner.phone}</div></div>}
                  </div>
                </div>
              )}
            </>
          )}

          {/* ── HISTORY TAB ──────────────────────────────────────── */}
          {activeTab === 'history' && (
            <div>
              <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: '600', color: '#2d3748' }}>{t('patientDetails.visitHistory')}</h3>
              {loadingHistory && <div style={{ padding: '2rem', textAlign: 'center', color: '#718096' }}>{t('patientDetails.loadingVisitHistory')}</div>}
              {historyError && <div style={{ padding: '1rem', backgroundColor: '#fff5f5', borderRadius: '6px', border: '1px solid #fed7d7', color: '#c53030' }}>{historyError}</div>}
              {!loadingHistory && !historyError && history.length === 0 && (
                <div style={{ padding: '2rem', textAlign: 'center', color: '#718096', backgroundColor: '#f7fafc', borderRadius: '6px' }}>{t('patientDetails.noVisitHistory')}</div>
              )}
              {!loadingHistory && history.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {history.map((entry) => {
                    const { services, medications, cleanNote } = parseNote(entry.note)
                    return (
                      <div key={entry.id} style={{ padding: '1.25rem', backgroundColor: '#f7fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                          <div>
                            <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#2d3748', marginBottom: '0.25rem' }}>
                              {t('patientDetails.visitDate')}: {formatDate(entry.visit_date || entry.created_at)}
                            </div>
                            {entry.created_by_name && <div style={{ fontSize: '0.8125rem', color: '#718096' }}>{t('patientDetails.recordedBy')}: {entry.created_by_name}</div>}
                          </div>
                          {entry.appointment && (
                            <div style={{ fontSize: '0.8125rem', color: '#718096', padding: '0.25rem 0.75rem', backgroundColor: 'white', borderRadius: '4px', border: '1px solid #cbd5e0' }}>
                              {t('patientDetails.appointment')} #{entry.appointment}
                            </div>
                          )}
                        </div>

                        {/* Services */}
                        {services.length > 0 && (
                          <div style={{ marginBottom: '0.75rem' }}>
                            <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#276749', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.375rem' }}>
                              {t('patientDetails.servicesPerformed', { defaultValue: 'Usługi' })}
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
                              {services.map((s, i) => (
                                <span key={i} style={{ padding: '0.25rem 0.625rem', backgroundColor: '#c6f6d5', color: '#22543d', borderRadius: '999px', fontSize: '0.8125rem', fontWeight: '500' }}>
                                  {s}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Medications */}
                        {medications.length > 0 && (
                          <div style={{ marginBottom: '0.75rem' }}>
                            <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#2b6cb0', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.375rem' }}>
                              {t('patientDetails.medicationsLabel', { defaultValue: 'Leki' })}
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
                              {medications.map((m, i) => (
                                <span key={i} style={{ padding: '0.25rem 0.625rem', backgroundColor: '#bee3f8', color: '#2a4365', borderRadius: '999px', fontSize: '0.8125rem', fontWeight: '500' }}>
                                  {m}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Clinical note */}
                        {cleanNote && (
                          <div>
                            <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#718096', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.375rem' }}>
                              {t('patientDetails.notesLabel')}
                            </div>
                            <div style={{ fontSize: '0.875rem', color: '#2d3748', padding: '0.75rem', backgroundColor: 'white', borderRadius: '6px', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{cleanNote}</div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* ── PRESCRIPTIONS TAB ────────────────────────────────── */}
          {activeTab === 'prescriptions' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: '600', color: '#2d3748', margin: 0 }}>{t('patientDetails.prescriptions.title')}</h3>
                {canWrite && !showAddForm && (
                  <button className="btn-primary" onClick={() => { setShowAddForm(true); setSaveError(null) }} style={{ fontSize: '0.875rem', padding: '0.4rem 0.9rem' }}>
                    + {t('patientDetails.prescriptions.add')}
                  </button>
                )}
              </div>

              {showAddForm && (
                <div style={{ marginBottom: '1.5rem', padding: '1.25rem', backgroundColor: '#f7fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <h4 style={{ margin: '0 0 1rem', fontSize: '0.95rem', fontWeight: '600', color: '#2d3748' }}>{t('patientDetails.prescriptions.newPrescription')}</h4>
                  {saveError && <div style={{ marginBottom: '0.75rem', padding: '0.6rem 0.9rem', backgroundColor: '#fff5f5', borderRadius: '6px', border: '1px solid #fed7d7', color: '#c53030', fontSize: '0.875rem' }}>{saveError}</div>}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                    <div>
                      <label style={labelStyle}>{t('patientDetails.prescriptions.drugName')} *</label>
                      <input style={inputStyle} value={form.drug_name} onChange={(e) => setForm((f) => ({ ...f, drug_name: e.target.value }))} placeholder={t('patientDetails.prescriptions.drugNamePlaceholder')} />
                    </div>
                    <div>
                      <label style={labelStyle}>{t('patientDetails.prescriptions.dosage')} *</label>
                      <input style={inputStyle} value={form.dosage} onChange={(e) => setForm((f) => ({ ...f, dosage: e.target.value }))} placeholder={t('patientDetails.prescriptions.dosagePlaceholder')} />
                    </div>
                    <div>
                      <label style={labelStyle}>{t('patientDetails.prescriptions.durationDays')}</label>
                      <input style={inputStyle} type="number" min="1" value={form.duration_days} onChange={(e) => setForm((f) => ({ ...f, duration_days: e.target.value }))} placeholder="e.g. 7" />
                    </div>
                  </div>
                  <div style={{ marginBottom: '0.75rem' }}>
                    <label style={labelStyle}>{t('patientDetails.prescriptions.notes')}</label>
                    <textarea style={{ ...inputStyle, resize: 'vertical', minHeight: '60px' }} value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} placeholder={t('patientDetails.prescriptions.notesPlaceholder')} />
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button className="btn-primary" disabled={saving || !form.drug_name.trim() || !form.dosage.trim()} onClick={handleAddPrescription}>
                      {saving ? t('common.saving') : t('common.save')}
                    </button>
                    <button className="btn-secondary" onClick={() => { setShowAddForm(false); setSaveError(null) }}>{t('common.cancel')}</button>
                  </div>
                </div>
              )}

              {loadingPrescriptions && <div style={{ padding: '2rem', textAlign: 'center', color: '#718096' }}>{t('patientDetails.prescriptions.loading')}</div>}
              {prescriptionsError && <div style={{ padding: '1rem', backgroundColor: '#fff5f5', borderRadius: '6px', border: '1px solid #fed7d7', color: '#c53030' }}>{prescriptionsError}</div>}
              {!loadingPrescriptions && !prescriptionsError && prescriptions.length === 0 && (
                <div style={{ padding: '2rem', textAlign: 'center', color: '#718096', backgroundColor: '#f7fafc', borderRadius: '6px' }}>{t('patientDetails.prescriptions.empty')}</div>
              )}
              {prescriptions.length > 0 && (
                <div className="inventory-table">
                  <table>
                    <thead>
                      <tr>
                        <th>{t('patientDetails.prescriptions.drugName')}</th>
                        <th>{t('patientDetails.prescriptions.dosage')}</th>
                        <th>{t('patientDetails.prescriptions.durationDays')}</th>
                        <th>{t('patientDetails.prescriptions.prescribedBy')}</th>
                        <th>{t('patientDetails.prescriptions.date')}</th>
                        <th>{t('patientDetails.prescriptions.notes')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {prescriptions.map((rx) => (
                        <tr key={rx.id}>
                          <td style={{ fontWeight: '500' }}>{rx.drug_name}</td>
                          <td>{rx.dosage}</td>
                          <td>{rx.duration_days ? `${rx.duration_days} ${t('patientDetails.prescriptions.days')}` : '—'}</td>
                          <td>{rx.prescribed_by_name || '—'}</td>
                          <td style={{ whiteSpace: 'nowrap', fontSize: '0.85rem' }}>{formatDateOnly(rx.created_at)}</td>
                          <td style={{ color: '#718096', fontSize: '0.85rem' }}>{rx.notes || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-actions" style={{ padding: '1rem 1.5rem', borderTop: '1px solid #e2e8f0' }}>
          <button type="button" className="btn-primary" onClick={onClose}>{t('patientDetails.close')}</button>
        </div>
      </div>
    </div>
  )
}

export default PatientDetailsModal
