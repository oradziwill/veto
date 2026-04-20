import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { patientHistoryAPI, patientAISummaryAPI, prescriptionsAPI, vaccinationsAPI } from '../../services/api'
import { translateSpecies } from '../../utils/species'
import SpeciesIcon from '../SpeciesIcon'
import AddAppointmentModal from './AddAppointmentModal'
import './Modal.css'


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
  const [showAddAppointment, setShowAddAppointment] = useState(false)

  // History
  const [history, setHistory] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [historyError, setHistoryError] = useState(null)

  // AI summary
  const [aiSummary, setAiSummary] = useState(null)
  const [loadingAISummary, setLoadingAISummary] = useState(false)
  const [aiSummaryError, setAiSummaryError] = useState(null)
  const [, setAiSummaryCached] = useState(false)

  // Vaccinations
  const [vaccinations, setVaccinations] = useState([])
  const [loadingVaccinations, setLoadingVaccinations] = useState(false)
  const [vaccinationsError, setVaccinationsError] = useState(null)
  const [showVaxForm, setShowVaxForm] = useState(false)
  const [savingVax, setSavingVax] = useState(false)
  const [saveVaxError, setSaveVaxError] = useState(null)
  const [vaxForm, setVaxForm] = useState({ vaccine_name: '', batch_number: '', administered_at: '', next_due_at: '', notes: '' })

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
  const hasFetchedVaxRef = useRef(false)
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
      setVaccinations([])
      setVaccinationsError(null)
      setShowVaxForm(false)
      setSaveVaxError(null)
      setVaxForm({ vaccine_name: '', batch_number: '', administered_at: '', next_due_at: '', notes: '' })
      hasFetchedRef.current = false
      hasFetchedAISummaryRef.current = false
      hasFetchedRxRef.current = false
      hasFetchedVaxRef.current = false
      currentPatientIdRef.current = null
      setActiveTab('overview')
      return
    }

    if (!patient?.id) return

    if (currentPatientIdRef.current !== patient.id) {
      hasFetchedRef.current = false
      hasFetchedAISummaryRef.current = false
      hasFetchedRxRef.current = false
      hasFetchedVaxRef.current = false
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

    if (!hasFetchedVaxRef.current) {
      hasFetchedVaxRef.current = true
      setLoadingVaccinations(true)
      vaccinationsAPI.list(patient.id)
        .then((res) => setVaccinations(res.data.results || res.data || []))
        .catch(() => {
          setVaccinationsError(t('patientDetails.vaccinations.loadError', { defaultValue: 'Failed to load vaccinations.' }))
          hasFetchedVaxRef.current = false
        })
        .finally(() => setLoadingVaccinations(false))
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

  const handleAddVaccination = async () => {
    setSavingVax(true)
    setSaveVaxError(null)
    try {
      const payload = {
        vaccine_name: vaxForm.vaccine_name,
        administered_at: vaxForm.administered_at,
        ...(vaxForm.batch_number ? { batch_number: vaxForm.batch_number } : {}),
        ...(vaxForm.next_due_at ? { next_due_at: vaxForm.next_due_at } : {}),
        ...(vaxForm.notes ? { notes: vaxForm.notes } : {}),
      }
      const res = await vaccinationsAPI.create(patient.id, payload)
      setVaccinations((prev) => [res.data, ...prev])
      setShowVaxForm(false)
      setVaxForm({ vaccine_name: '', batch_number: '', administered_at: '', next_due_at: '', notes: '' })
    } catch (err) {
      const data = err.response?.data
      setSaveVaxError(data ? Object.values(data).flat().join(' ') : t('patientDetails.vaccinations.saveError', { defaultValue: 'Failed to save vaccination.' }))
    } finally {
      setSavingVax(false)
    }
  }

  const handleDeleteVaccination = async (id) => {
    if (!window.confirm(t('patientDetails.vaccinations.confirmDelete', { defaultValue: 'Delete this vaccination record?' }))) return
    try {
      await vaccinationsAPI.delete(id)
      setVaccinations((prev) => prev.filter((v) => v.id !== id))
    } catch {
      // silently ignore
    }
  }

  const canWrite = userRole === 'doctor' || userRole === 'admin'

  if (!isOpen || !patient) return null

  const inputStyle = { width: '100%', padding: '0.5rem 0.75rem', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '0.9rem', boxSizing: 'border-box' }
  const labelStyle = { display: 'block', fontSize: '0.75rem', fontWeight: '600', color: '#a0aec0', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }

  const speciesColor = '#16a34a'

  const nextVax = vaccinations
    .filter(v => v.next_due_at)
    .sort((a, b) => new Date(a.next_due_at) - new Date(b.next_due_at))[0]
  const nextVaxOverdue = nextVax && new Date(nextVax.next_due_at) < new Date()

  const statCards = [
    { key: 'history', icon: '🏥', label: t('patientDetails.tabs.history'), count: history.length, color: '#16a34a', bg: '#f0fff4' },
    { key: 'vaccinations', icon: '💉', label: t('patientDetails.tabs.vaccinations'), count: vaccinations.length, color: '#38a169', bg: '#f0fff4', alert: nextVaxOverdue },
    { key: 'prescriptions', icon: '💊', label: t('patientDetails.tabs.prescriptions'), count: prescriptions.length, color: '#16a34a', bg: '#f0fff4' },
  ]

  return (
    <>
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '960px', maxHeight: '92vh', overflowY: 'auto', padding: 0, borderRadius: '12px' }}>

        {/* ── PATIENT HEADER ─────────────────────────────────────── */}
        <div style={{ background: 'linear-gradient(135deg, #1a2e20 0%, #2a4a30 100%)', padding: '1.5rem 1.75rem', borderRadius: '12px 12px 0 0', position: 'relative' }}>
          <button onClick={onClose} style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'rgba(255,255,255,0.1)', border: 'none', color: 'white', width: '2rem', height: '2rem', borderRadius: '50%', cursor: 'pointer', fontSize: '1.1rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>×</button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
            <div style={{ width: '64px', height: '64px', borderRadius: '16px', background: `${speciesColor}22`, border: `2px solid ${speciesColor}55`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <SpeciesIcon species={patient.species} size={40} color={speciesColor} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: '700', color: 'white' }}>{patient.name}</h2>
                <span style={{ padding: '0.2rem 0.7rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: '600', background: `${speciesColor}33`, color: speciesColor, border: `1px solid ${speciesColor}55` }}>
                  {patient.species ? translateSpecies(patient.species, t) : '—'}
                </span>
                {patient.allergies && (
                  <span style={{ padding: '0.2rem 0.7rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: '600', background: '#c530301a', color: '#fc8181', border: '1px solid #c5303033' }}>
                    ⚠ {t('patientDetails.allergies')}
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', gap: '1.25rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                {patient.breed && <span style={{ fontSize: '0.875rem', color: '#a0aec0' }}>{patient.breed}</span>}
                {patient.sex && <span style={{ fontSize: '0.875rem', color: '#a0aec0' }}>· {patient.sex}</span>}
                {patient.birth_date && <span style={{ fontSize: '0.875rem', color: '#a0aec0' }}>· {calculateAge(patient.birth_date)}</span>}
                {patient.microchip_no && <span style={{ fontSize: '0.8rem', color: '#718096', fontFamily: 'monospace' }}>🔖 {patient.microchip_no}</span>}
              </div>
            </div>
            {patient.owner && (
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontSize: '0.75rem', color: '#718096', marginBottom: '0.2rem' }}>{t('patientDetails.ownerInfo')}</div>
                <div style={{ fontSize: '0.9rem', fontWeight: '600', color: '#e2e8f0' }}>{patient.owner.first_name} {patient.owner.last_name}</div>
                {patient.owner.phone && <div style={{ fontSize: '0.8rem', color: '#a0aec0' }}>{patient.owner.phone}</div>}
              </div>
            )}
          </div>

          {/* Stat chips */}
          <div style={{ display: 'flex', gap: '0.625rem', marginTop: '1.25rem', alignItems: 'center' }}>
            {statCards.map(sc => (
              <button key={sc.key} onClick={() => setActiveTab(sc.key)}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0.875rem', borderRadius: '999px', border: activeTab === sc.key ? `2px solid ${sc.color}` : '2px solid transparent', background: activeTab === sc.key ? sc.bg : 'rgba(255,255,255,0.08)', cursor: 'pointer', transition: 'all 0.15s' }}>
                <span style={{ fontSize: '0.875rem' }}>{sc.icon}</span>
                <span style={{ fontSize: '0.8rem', fontWeight: '600', color: activeTab === sc.key ? sc.color : '#cbd5e0' }}>{sc.label}</span>
                <span style={{ fontSize: '0.75rem', fontWeight: '700', padding: '0.05rem 0.45rem', borderRadius: '999px', background: activeTab === sc.key ? sc.color : 'rgba(255,255,255,0.15)', color: activeTab === sc.key ? 'white' : '#cbd5e0' }}>
                  {sc.count}
                </span>
                {sc.alert && <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#fc8181', flexShrink: 0 }} />}
              </button>
            ))}
            <button onClick={() => setActiveTab('overview')}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0.875rem', borderRadius: '999px', border: activeTab === 'overview' ? '2px solid #e2e8f0' : '2px solid transparent', background: activeTab === 'overview' ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.05)', cursor: 'pointer' }}>
              <span style={{ fontSize: '0.875rem' }}>📋</span>
              <span style={{ fontSize: '0.8rem', fontWeight: '600', color: activeTab === 'overview' ? '#e2e8f0' : '#718096' }}>{t('patientDetails.tabs.overview')}</span>
            </button>
            <button onClick={() => setShowAddAppointment(true)} style={{ marginLeft: 'auto', background: '#22c55e', border: 'none', color: 'white', padding: '0.45rem 1rem', borderRadius: '8px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '0.4rem', whiteSpace: 'nowrap', boxShadow: '0 2px 8px rgba(34,197,94,0.4)' }}>
              📅 {t('patientDetails.scheduleAppointment', { defaultValue: 'Umów na wizytę' })}
            </button>
          </div>
        </div>

        {/* ── CONTENT ────────────────────────────────────────────── */}
        <div style={{ padding: '1.75rem', minHeight: '400px' }}>

          {/* ── OVERVIEW TAB ─────────────────────────────────────── */}
          {activeTab === 'overview' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>

              {/* Left column */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                <div style={{ background: '#f7fafc', borderRadius: '10px', padding: '1.25rem', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '0.7rem', fontWeight: '700', color: '#a0aec0', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '1rem' }}>{t('patientDetails.patientInfo')}</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem' }}>
                    {[
                      [t('patientDetails.species'), patient.species ? translateSpecies(patient.species, t) : '—'],
                      [t('patientDetails.breed'), patient.breed || '—'],
                      [t('patientDetails.sex'), patient.sex || '—'],
                      [t('patientDetails.birthDate'), patient.birth_date ? formatDateOnly(patient.birth_date) : '—'],
                      [t('patientDetails.age'), calculateAge(patient.birth_date)],
                      ...(patient.microchip_no ? [[t('patientDetails.microchipNumber'), patient.microchip_no]] : []),
                    ].map(([label, value]) => (
                      <div key={label}>
                        <div style={labelStyle}>{label}</div>
                        <div style={{ fontWeight: '500', color: '#2d3748', fontSize: '0.9rem' }}>{value}</div>
                      </div>
                    ))}
                  </div>
                  {patient.allergies && (
                    <div style={{ marginTop: '1rem', padding: '0.625rem 0.875rem', background: '#fff5f5', borderRadius: '6px', border: '1px solid #fed7d7', fontSize: '0.875rem', color: '#c53030' }}>
                      ⚠ <strong>{t('patientDetails.allergies')}:</strong> {patient.allergies}
                    </div>
                  )}
                  {patient.notes && (
                    <div style={{ marginTop: '0.75rem' }}>
                      <div style={labelStyle}>{t('patientDetails.notes')}</div>
                      <div style={{ fontSize: '0.875rem', color: '#4a5568', whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>{patient.notes}</div>
                    </div>
                  )}
                </div>

                {patient.owner && (
                  <div style={{ background: '#f7fafc', borderRadius: '10px', padding: '1.25rem', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '0.7rem', fontWeight: '700', color: '#a0aec0', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '1rem' }}>{t('patientDetails.ownerInfo')}</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                      <div>
                        <div style={labelStyle}>{t('patientDetails.ownerName')}</div>
                        <div style={{ fontWeight: '600', color: '#2d3748' }}>{patient.owner.first_name} {patient.owner.last_name}</div>
                      </div>
                      {patient.owner.email && <div><div style={labelStyle}>{t('patientDetails.email')}</div><div style={{ color: '#3182ce', fontSize: '0.9rem' }}>{patient.owner.email}</div></div>}
                      {patient.owner.phone && <div><div style={labelStyle}>{t('patientDetails.phone')}</div><div style={{ fontWeight: '500', color: '#2d3748' }}>{patient.owner.phone}</div></div>}
                    </div>
                  </div>
                )}
              </div>

              {/* Right column — AI summary */}
              <div style={{ background: '#f0f9ff', borderRadius: '10px', padding: '1.25rem', border: '1px solid #bee3f8' }}>
                <div style={{ fontSize: '0.7rem', fontWeight: '700', color: '#276749', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '1rem' }}>✨ {t('patientDetails.aiSummary')}</div>
                {loadingAISummary && (
                  <div style={{ textAlign: 'center', color: '#718096', paddingTop: '2rem' }}>
                    <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🤔</div>
                    <div style={{ fontWeight: '500' }}>{t('patientDetails.generatingSummary')}</div>
                    <div style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>{t('patientDetails.analyzingHistory')}</div>
                  </div>
                )}
                {aiSummaryError && !loadingAISummary && (
                  <div style={{ color: '#c53030', fontSize: '0.875rem' }}>
                    <div>{aiSummaryError}</div>
                    <button onClick={async () => {
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
                    }} style={{ marginTop: '0.75rem', padding: '0.4rem 0.875rem', background: '#3182ce', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: '600' }}>
                      {t('common.retry')}
                    </button>
                  </div>
                )}
                {aiSummary && !loadingAISummary && (
                  <div style={{ fontSize: '0.875rem', color: '#2d3748', whiteSpace: 'pre-wrap', lineHeight: '1.8' }}>{aiSummary}</div>
                )}
                {!aiSummary && !loadingAISummary && !aiSummaryError && (
                  <div style={{ textAlign: 'center', color: '#a0aec0', paddingTop: '2rem', fontSize: '0.875rem' }}>Brak podsumowania.</div>
                )}
              </div>
            </div>
          )}

          {/* ── HISTORY TAB ──────────────────────────────────────── */}
          {activeTab === 'history' && (
            <div>
              {loadingHistory && <div style={{ padding: '3rem', textAlign: 'center', color: '#718096' }}>{t('patientDetails.loadingVisitHistory')}</div>}
              {historyError && <div style={{ padding: '1rem', background: '#fff5f5', borderRadius: '8px', border: '1px solid #fed7d7', color: '#c53030' }}>{historyError}</div>}
              {!loadingHistory && !historyError && history.length === 0 && (
                <div style={{ padding: '3rem', textAlign: 'center', color: '#a0aec0' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>🏥</div>
                  <div style={{ fontWeight: '500' }}>{t('patientDetails.noVisitHistory')}</div>
                </div>
              )}
              {!loadingHistory && history.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
                  {history.map((entry, idx) => {
                    const { services, medications, cleanNote } = parseNote(entry.note)
                    return (
                      <div key={entry.id} style={{ display: 'flex', gap: '1rem' }}>
                        {/* Timeline spine */}
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
                          <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#3182ce', border: '2px solid #ebf8ff', marginTop: '1.25rem', flexShrink: 0 }} />
                          {idx < history.length - 1 && <div style={{ width: '2px', flex: 1, background: '#e2e8f0', marginTop: '0.25rem' }} />}
                        </div>

                        <div style={{ flex: 1, paddingBottom: '1.25rem' }}>
                          <div style={{ background: 'white', borderRadius: '10px', border: '1px solid #e2e8f0', padding: '1rem 1.25rem', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: services.length > 0 || medications.length > 0 || cleanNote ? '0.875rem' : 0 }}>
                              <div>
                                <div style={{ fontWeight: '600', color: '#1a202c', fontSize: '0.9rem' }}>{formatDate(entry.visit_date || entry.created_at)}</div>
                                {entry.created_by_name && <div style={{ fontSize: '0.8rem', color: '#a0aec0', marginTop: '0.125rem' }}>Dr {entry.created_by_name}</div>}
                              </div>
                              {entry.appointment && (
                                <span style={{ fontSize: '0.75rem', color: '#718096', padding: '0.2rem 0.6rem', background: '#f7fafc', borderRadius: '999px', border: '1px solid #e2e8f0' }}>
                                  #{typeof entry.appointment === 'object' ? entry.appointment.id : entry.appointment}
                                </span>
                              )}
                            </div>

                            {services.length > 0 && (
                              <div style={{ marginBottom: '0.625rem' }}>
                                <div style={{ fontSize: '0.7rem', fontWeight: '700', color: '#276749', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.375rem' }}>
                                  {t('patientDetails.servicesPerformed', { defaultValue: 'Usługi' })}
                                </div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
                                  {services.map((s, i) => (
                                    <span key={i} style={{ padding: '0.2rem 0.6rem', background: '#c6f6d5', color: '#22543d', borderRadius: '999px', fontSize: '0.8rem', fontWeight: '500' }}>{s}</span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {medications.length > 0 && (
                              <div style={{ marginBottom: '0.625rem' }}>
                                <div style={{ fontSize: '0.7rem', fontWeight: '700', color: '#276749', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.375rem' }}>
                                  {t('patientDetails.medicationsLabel', { defaultValue: 'Leki' })}
                                </div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
                                  {medications.map((m, i) => (
                                    <span key={i} style={{ padding: '0.2rem 0.6rem', background: '#c6f6d5', color: '#22543d', borderRadius: '999px', fontSize: '0.8rem', fontWeight: '500' }}>{m}</span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {cleanNote && (
                              <div style={{ fontSize: '0.8375rem', color: '#4a5568', background: '#f7fafc', borderRadius: '6px', padding: '0.625rem 0.875rem', whiteSpace: 'pre-wrap', lineHeight: '1.6', borderLeft: '3px solid #e2e8f0' }}>
                                {cleanNote}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* ── VACCINATIONS TAB ─────────────────────────────────── */}
          {activeTab === 'vaccinations' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
                {canWrite && !showVaxForm && (
                  <button className="btn-primary" onClick={() => { setShowVaxForm(true); setSaveVaxError(null) }} style={{ fontSize: '0.875rem' }}>
                    + {t('patientDetails.vaccinations.add', { defaultValue: 'Dodaj szczepienie' })}
                  </button>
                )}
              </div>

              {showVaxForm && (
                <div style={{ marginBottom: '1.25rem', padding: '1.25rem', background: '#f7fafc', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                    <div>
                      <label style={labelStyle}>{t('patientDetails.vaccinations.vaccineName', { defaultValue: 'Nazwa szczepionki' })} *</label>
                      <input style={inputStyle} value={vaxForm.vaccine_name} onChange={e => setVaxForm(f => ({ ...f, vaccine_name: e.target.value }))} placeholder="np. Vanguard Plus 5" />
                    </div>
                    <div>
                      <label style={labelStyle}>{t('patientDetails.vaccinations.batchNumber', { defaultValue: 'Numer serii' })}</label>
                      <input style={inputStyle} value={vaxForm.batch_number} onChange={e => setVaxForm(f => ({ ...f, batch_number: e.target.value }))} />
                    </div>
                    <div>
                      <label style={labelStyle}>{t('patientDetails.vaccinations.administeredAt', { defaultValue: 'Data podania' })} *</label>
                      <input type="date" style={inputStyle} value={vaxForm.administered_at} onChange={e => setVaxForm(f => ({ ...f, administered_at: e.target.value }))} />
                    </div>
                    <div>
                      <label style={labelStyle}>{t('patientDetails.vaccinations.nextDueAt', { defaultValue: 'Następna dawka' })}</label>
                      <input type="date" style={inputStyle} value={vaxForm.next_due_at} onChange={e => setVaxForm(f => ({ ...f, next_due_at: e.target.value }))} />
                    </div>
                    <div style={{ gridColumn: '1 / -1' }}>
                      <label style={labelStyle}>{t('patientDetails.vaccinations.notes', { defaultValue: 'Uwagi' })}</label>
                      <input style={inputStyle} value={vaxForm.notes} onChange={e => setVaxForm(f => ({ ...f, notes: e.target.value }))} />
                    </div>
                  </div>
                  {saveVaxError && <div style={{ color: '#c53030', fontSize: '0.875rem', marginBottom: '0.5rem' }}>{saveVaxError}</div>}
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button className="btn-primary" onClick={handleAddVaccination} disabled={savingVax || !vaxForm.vaccine_name || !vaxForm.administered_at}>
                      {savingVax ? t('common.saving', { defaultValue: 'Zapisuję...' }) : t('common.save', { defaultValue: 'Zapisz' })}
                    </button>
                    <button className="btn-secondary" onClick={() => { setShowVaxForm(false); setSaveVaxError(null) }}>{t('common.cancel')}</button>
                  </div>
                </div>
              )}

              {loadingVaccinations && <div style={{ padding: '3rem', textAlign: 'center', color: '#718096' }}>Ładowanie...</div>}
              {vaccinationsError && <div style={{ padding: '1rem', background: '#fff5f5', borderRadius: '8px', border: '1px solid #fed7d7', color: '#c53030' }}>{vaccinationsError}</div>}
              {!loadingVaccinations && vaccinations.length === 0 && !showVaxForm && (
                <div style={{ padding: '3rem', textAlign: 'center', color: '#a0aec0' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>💉</div>
                  <div style={{ fontWeight: '500' }}>{t('patientDetails.vaccinations.empty', { defaultValue: 'Brak rekordów szczepień.' })}</div>
                </div>
              )}
              {vaccinations.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                  {vaccinations.map((v) => {
                    const isOverdue = v.next_due_at && new Date(v.next_due_at) < new Date()
                    const isDueSoon = v.next_due_at && !isOverdue && (new Date(v.next_due_at) - new Date()) < 30 * 24 * 60 * 60 * 1000
                    return (
                      <div key={v.id} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.875rem 1.125rem', background: 'white', borderRadius: '10px', border: `1px solid ${isOverdue ? '#fed7d7' : '#e2e8f0'}`, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
                        <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: isOverdue ? '#fff5f5' : '#f0fff4', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem', flexShrink: 0 }}>💉</div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span style={{ fontWeight: '600', color: '#1a202c', fontSize: '0.9375rem' }}>{v.vaccine_name}</span>
                            {isOverdue && <span style={{ padding: '0.1rem 0.5rem', background: '#fed7d7', color: '#c53030', borderRadius: '999px', fontSize: '0.7rem', fontWeight: '700' }}>PRZETERMINOWANE</span>}
                            {isDueSoon && <span style={{ padding: '0.1rem 0.5rem', background: '#fef3c7', color: '#92400e', borderRadius: '999px', fontSize: '0.7rem', fontWeight: '700' }}>WKRÓTCE</span>}
                          </div>
                          <div style={{ display: 'flex', gap: '1.25rem', marginTop: '0.25rem', flexWrap: 'wrap' }}>
                            <span style={{ fontSize: '0.8rem', color: '#718096' }}>Podano: <strong style={{ color: '#2d3748' }}>{formatDateOnly(v.administered_at)}</strong></span>
                            {v.next_due_at && <span style={{ fontSize: '0.8rem', color: '#718096' }}>Kolejna: <strong style={{ color: isOverdue ? '#c53030' : '#2d3748' }}>{formatDateOnly(v.next_due_at)}</strong></span>}
                            {v.batch_number && <span style={{ fontSize: '0.8rem', color: '#a0aec0', fontFamily: 'monospace' }}>{v.batch_number}</span>}
                            {v.administered_by_name && <span style={{ fontSize: '0.8rem', color: '#a0aec0' }}>Dr {v.administered_by_name}</span>}
                          </div>
                          {v.notes && <div style={{ marginTop: '0.25rem', fontSize: '0.8rem', color: '#718096', fontStyle: 'italic' }}>{v.notes}</div>}
                        </div>
                        {canWrite && (
                          <button onClick={() => handleDeleteVaccination(v.id)} style={{ background: 'none', border: 'none', color: '#cbd5e0', cursor: 'pointer', fontSize: '1.25rem', padding: '0.25rem', lineHeight: 1, flexShrink: 0, borderRadius: '4px' }} title={t('common.delete')}>×</button>
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
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
                {canWrite && !showAddForm && (
                  <button className="btn-primary" onClick={() => { setShowAddForm(true); setSaveError(null) }} style={{ fontSize: '0.875rem' }}>
                    + {t('patientDetails.prescriptions.add')}
                  </button>
                )}
              </div>

              {showAddForm && (
                <div style={{ marginBottom: '1.25rem', padding: '1.25rem', background: '#f7fafc', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                  <h4 style={{ margin: '0 0 1rem', fontSize: '0.95rem', fontWeight: '600', color: '#2d3748' }}>{t('patientDetails.prescriptions.newPrescription')}</h4>
                  {saveError && <div style={{ marginBottom: '0.75rem', padding: '0.6rem 0.9rem', background: '#fff5f5', borderRadius: '6px', border: '1px solid #fed7d7', color: '#c53030', fontSize: '0.875rem' }}>{saveError}</div>}
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
                      <input style={inputStyle} type="number" min="1" value={form.duration_days} onChange={(e) => setForm((f) => ({ ...f, duration_days: e.target.value }))} placeholder="np. 7" />
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

              {loadingPrescriptions && <div style={{ padding: '3rem', textAlign: 'center', color: '#718096' }}>{t('patientDetails.prescriptions.loading')}</div>}
              {prescriptionsError && <div style={{ padding: '1rem', background: '#fff5f5', borderRadius: '8px', border: '1px solid #fed7d7', color: '#c53030' }}>{prescriptionsError}</div>}
              {!loadingPrescriptions && prescriptions.length === 0 && !showAddForm && (
                <div style={{ padding: '3rem', textAlign: 'center', color: '#a0aec0' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>💊</div>
                  <div style={{ fontWeight: '500' }}>{t('patientDetails.prescriptions.empty')}</div>
                </div>
              )}
              {prescriptions.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                  {prescriptions.map((rx) => (
                    <div key={rx.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', padding: '0.875rem 1.125rem', background: 'white', borderRadius: '10px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
                      <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: '#f0fff4', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem', flexShrink: 0 }}>💊</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: '600', color: '#1a202c', fontSize: '0.9375rem', marginBottom: '0.25rem' }}>{rx.drug_name}</div>
                        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '0.8rem', color: '#718096' }}>{rx.dosage}</span>
                          {rx.duration_days && <span style={{ fontSize: '0.8rem', color: '#718096' }}>{rx.duration_days} {t('patientDetails.prescriptions.days')}</span>}
                          {rx.prescribed_by_name && <span style={{ fontSize: '0.8rem', color: '#a0aec0' }}>Dr {rx.prescribed_by_name}</span>}
                          <span style={{ fontSize: '0.8rem', color: '#a0aec0' }}>{formatDateOnly(rx.created_at)}</span>
                        </div>
                        {rx.notes && <div style={{ marginTop: '0.25rem', fontSize: '0.8rem', color: '#718096', fontStyle: 'italic' }}>{rx.notes}</div>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>

    <AddAppointmentModal
      isOpen={showAddAppointment}
      onClose={() => setShowAddAppointment(false)}
      onSuccess={() => setShowAddAppointment(false)}
      initialOwner={patient?.owner}
      initialPatient={patient}
    />
    </>
  )
}

export default PatientDetailsModal
