import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  appointmentsAPI,
  patientsAPI,
  clientsAPI,
  patientHistoryAPI,
  servicesAPI,
  invoicesAPI,
  inventoryAPI,
} from '../../services/api'
import AddClientModal from './AddClientModal'
import './Modal.css'

import { translateSpecies } from '../../utils/species'

const VITAL_FIELD_CONFIGS = {
  Dog: [
    { section: 'Podstawowe parametry życiowe', fields: [
      { key: 'temperatura', label: 'Temperatura', default: '38.5', unit: '°C' },
      { key: 'tetno', label: 'Tętno', default: '90', unit: 'bpm' },
      { key: 'oddechy', label: 'Oddechy', default: '20', unit: '/min' },
    ]},
    { section: 'Stan ogólny', fields: [
      { key: 'zachowanie', label: 'Zachowanie', default: 'spokojny / czujny' },
      { key: 'bcs', label: 'BCS', default: '5/9' },
      { key: 'nawodnienie', label: 'Nawodnienie', default: 'prawidłowe' },
    ]},
    { section: 'Badanie kliniczne', fields: [
      { key: 'blony_sluzowe', label: 'Błony śluzowe', default: 'różowe, wilgotne' },
      { key: 'crt', label: 'CRT', default: '< 2 s' },
      { key: 'wezly_chlonne', label: 'Węzły chłonne', default: 'niepowiększone' },
      { key: 'serce', label: 'Osłuchiwanie serca', default: 'bez szmerów' },
      { key: 'pluca', label: 'Osłuchiwanie płuc', default: 'prawidłowe' },
    ]},
    { section: 'Dodatkowe', fields: [
      { key: 'apetyt', label: 'Apetyt', default: 'prawidłowy' },
      { key: 'mocz_kal', label: 'Oddawanie moczu/kału', default: 'prawidłowe' },
      { key: 'szczepienia', label: 'Szczepienia', default: 'aktualne' },
    ]},
  ],
  Cat: [
    { section: 'Podstawowe parametry', fields: [
      { key: 'temperatura', label: 'Temperatura', default: '38.5', unit: '°C' },
      { key: 'tetno', label: 'Tętno', default: '160', unit: 'bpm' },
      { key: 'oddechy', label: 'Oddechy', default: '25', unit: '/min' },
    ]},
    { section: 'Stan ogólny', fields: [
      { key: 'zachowanie', label: 'Zachowanie', default: 'czujny (ew. lekko zestresowany)' },
      { key: 'bcs', label: 'BCS', default: '5/9' },
      { key: 'nawodnienie', label: 'Nawodnienie', default: 'prawidłowe' },
    ]},
    { section: 'Badanie kliniczne', fields: [
      { key: 'blony_sluzowe', label: 'Błony śluzowe', default: 'różowe' },
      { key: 'crt', label: 'CRT', default: '< 2 s' },
      { key: 'serce', label: 'Serce', default: 'rytmy prawidłowe' },
      { key: 'pluca', label: 'Płuca', default: 'bez zmian osłuchowych' },
      { key: 'oczy_uszy', label: 'Oczy/uszy', default: 'bez zmian' },
    ]},
    { section: 'Dodatkowe', fields: [
      { key: 'apetyt', label: 'Apetyt', default: 'prawidłowy' },
      { key: 'kuweta', label: 'Kuweta', default: 'prawidłowa' },
      { key: 'szczepienia', label: 'Szczepienia', default: 'aktualne' },
    ]},
  ],
  Rabbit: [
    { section: 'Podstawowe parametry', fields: [
      { key: 'temperatura', label: 'Temperatura', default: '39.5', unit: '°C' },
      { key: 'tetno', label: 'Tętno', default: '200', unit: 'bpm' },
      { key: 'oddechy', label: 'Oddechy', default: '40', unit: '/min' },
    ]},
    { section: 'Stan ogólny', fields: [
      { key: 'zachowanie', label: 'Zachowanie', default: 'czujny' },
      { key: 'bcs', label: 'BCS', default: '3/5' },
      { key: 'nawodnienie', label: 'Nawodnienie', default: 'prawidłowe' },
    ]},
    { section: 'Badanie kliniczne', fields: [
      { key: 'zeby', label: 'Zęby', default: 'prawidłowe (brak przerostu)' },
      { key: 'brzuch', label: 'Brzuch', default: 'miękki, niebolesny' },
      { key: 'perystaltyka', label: 'Perystaltyka', default: 'obecna' },
      { key: 'blony_sluzowe', label: 'Błony śluzowe', default: 'różowe' },
    ]},
    { section: 'Dodatkowe', fields: [
      { key: 'apetyt', label: 'Apetyt', default: 'prawidłowy' },
      { key: 'kal', label: 'Kał', default: 'prawidłowe bobki' },
      { key: 'aktywnosc', label: 'Aktywność', default: 'prawidłowa' },
    ]},
  ],
}

const initVitalParams = (species) => {
  const config = VITAL_FIELD_CONFIGS[species]
  if (!config) return {}
  const defaults = {}
  config.forEach(section => section.fields.forEach(f => { defaults[f.key] = f.default }))
  return defaults
}

const StartVisitModal = ({ isOpen, onClose, onSuccess, initialPatient = null, initialChiefComplaint = '', standalone = false }) => {
  const { t } = useTranslation()
  const [ownerSearch, setOwnerSearch] = useState('')
  const [ownerSearchResults, setOwnerSearchResults] = useState([])
  const [selectedOwner, setSelectedOwner] = useState(null)
  const [showOwnerDropdown, setShowOwnerDropdown] = useState(false)
  const [patients, setPatients] = useState([])
  const [loadingPatients, setLoadingPatients] = useState(false)
  const [searchingClients, setSearchingClients] = useState(false)
  const [showClientModal, setShowClientModal] = useState(false)
  
  const [formData, setFormData] = useState({
    patient: '',
    visitNotes: '',
    medicalReceipts: '',
    additionalNotes: '',
  })

  const [vitalParams, setVitalParams] = useState({})
  const [patientSpecies, setPatientSpecies] = useState('Dog')

  const [services, setServices] = useState([])
  const [selectedServices, setSelectedServices] = useState([]) // { id, name, price } - can add same service multiple times
  const [serviceToAdd, setServiceToAdd] = useState('') // id of service selected in dropdown
  const [loadingServices, setLoadingServices] = useState(false)
  const [servicesError, setServicesError] = useState(false)
  const [servicesFetchKey, setServicesFetchKey] = useState(0)

  const [medicationItems, setMedicationItems] = useState([])
  const [loadingMedications, setLoadingMedications] = useState(false)
  const [selectedMedications, setSelectedMedications] = useState([]) // { id, name, unit, quantity }
  const [medicationToAdd, setMedicationToAdd] = useState('')
  const [medicationQty, setMedicationQty] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [suggestedAppointment, setSuggestedAppointment] = useState(null)

  // Fetch services and medications when modal opens
  useEffect(() => {
    if (!isOpen) return
    let cancelled = false

    setLoadingServices(true)
    setServicesError(false)
    setSelectedServices([])
    setServiceToAdd('')
    setSelectedMedications([])
    setMedicationToAdd('')
    setMedicationQty(1)

    servicesAPI.list()
      .then(response => {
        if (cancelled) return
        const data = response.data.results ?? response.data ?? []
        setServices(Array.isArray(data) ? data : [])
      })
      .catch(err => {
        if (cancelled) return
        console.error('Error loading services:', err)
        setServicesError(true)
        setServices([])
      })
      .finally(() => {
        if (!cancelled) setLoadingServices(false)
      })

    setLoadingMedications(true)
    inventoryAPI.list({ category: 'medication', page_size: 200 })
      .then(res => {
        if (cancelled) return
        setMedicationItems(res.data.results ?? res.data ?? [])
      })
      .catch(() => { if (!cancelled) setMedicationItems([]) })
      .finally(() => { if (!cancelled) setLoadingMedications(false) })

    return () => { cancelled = true }
  }, [isOpen, servicesFetchKey])

  // On open: pre-fill from queue entry OR check for scheduled appointment
  useEffect(() => {
    if (!isOpen) return

    if (initialPatient) {
      // Pre-fill from waiting room queue entry
      setSuggestedAppointment(null)
      setError(null)
      setOwnerSearchResults([])
      setShowOwnerDropdown(false)

      const owner = initialPatient.owner
      if (owner) {
        setSelectedOwner(owner)
        setOwnerSearch(`${owner.first_name} ${owner.last_name}`)
        loadPatientsForOwner(owner.id)
      }
      setPatientSpecies(initialPatient.species || null)
      setVitalParams(initVitalParams(initialPatient.species))
      setFormData({
        patient: initialPatient.id.toString(),
        visitNotes: initialChiefComplaint || '',
        medicalReceipts: '',
        additionalNotes: '',
      })
      return
    }

    // Default: reset form and check for scheduled appointment
    setFormData({
      patient: '',
      visitNotes: '',
      medicalReceipts: '',
      additionalNotes: '',
    })
    setPatientSpecies('Dog')
    setVitalParams({})
    setOwnerSearch('')
    setSelectedOwner(null)
    setOwnerSearchResults([])
    setShowOwnerDropdown(false)
    setPatients([])
    setError(null)
    setSuggestedAppointment(null)

    const checkCurrentAppointment = async () => {
      try {
        const now = new Date()
        const futureTime = new Date(now.getTime() + 30 * 60 * 1000)

        const response = await appointmentsAPI.list()
        const allAppointments = response.data.results || response.data || []

        const currentAppointment = allAppointments.find(apt => {
          const aptStart = new Date(apt.starts_at)
          const aptEnd = new Date(apt.ends_at || apt.starts_at)
          return aptStart <= futureTime && aptEnd >= now && apt.status !== 'cancelled'
        })

        if (currentAppointment) {
          setSuggestedAppointment(currentAppointment)
          if (currentAppointment.patient?.owner) {
            const patient = currentAppointment.patient
            setSelectedOwner(patient.owner)
            setOwnerSearch(`${patient.owner.first_name} ${patient.owner.last_name}`)
            setPatientSpecies(patient.species || null)
            setVitalParams(initVitalParams(patient.species))
            setFormData(prev => ({ ...prev, patient: patient.id.toString() }))
            loadPatientsForOwner(patient.owner.id)
          }
        }
      } catch (err) {
        console.error('Error checking current appointment:', err)
      }
    }

    checkCurrentAppointment()
  }, [isOpen, initialPatient, initialChiefComplaint])

  const loadPatientsForOwner = async (ownerId) => {
    try {
      setLoadingPatients(true)
      const response = await patientsAPI.list({ owner: ownerId })
      const patientsData = response.data.results || response.data
      setPatients(patientsData)
    } catch (err) {
      console.error('Error loading patients:', err)
      setPatients([])
    } finally {
      setLoadingPatients(false)
    }
  }

  // Search for clients when ownerSearch changes
  useEffect(() => {
    const searchClients = async () => {
      if (ownerSearch.trim().length < 2) {
        setOwnerSearchResults([])
        setShowOwnerDropdown(false)
        return
      }

      try {
        setSearchingClients(true)
        const response = await clientsAPI.list({ search: ownerSearch.trim() })
        const results = response.data.results || response.data
        setOwnerSearchResults(results)
        setShowOwnerDropdown(results.length > 0)
      } catch (err) {
        console.error('Error searching clients:', err)
        setOwnerSearchResults([])
        setShowOwnerDropdown(false)
      } finally {
        setSearchingClients(false)
      }
    }

    const timeoutId = setTimeout(searchClients, 300) // Debounce search
    return () => clearTimeout(timeoutId)
  }, [ownerSearch])

  // Load patients when owner is selected
  useEffect(() => {
    if (selectedOwner?.id) {
      loadPatientsForOwner(selectedOwner.id)
    } else {
      setPatients([])
      setFormData(prev => ({ ...prev, patient: '' }))
    }
  }, [selectedOwner])

  const handleOwnerSearchChange = (e) => {
    const value = e.target.value
    setOwnerSearch(value)
    if (!value) {
      setSelectedOwner(null)
      setFormData(prev => ({ ...prev, patient: '' }))
      setPatients([])
      setShowOwnerDropdown(false)
    }
  }

  const handleOwnerSelect = (client) => {
    setSelectedOwner(client)
    setOwnerSearch(`${client.first_name} ${client.last_name}`)
    setFormData(prev => ({ ...prev, patient: '' })) // Clear patient when owner changes
    setShowOwnerDropdown(false)
    setOwnerSearchResults([])
  }

  const handleNewClientCreated = (newClient) => {
    setSelectedOwner(newClient)
    setOwnerSearch(`${newClient.first_name} ${newClient.last_name}`)
    setShowClientModal(false)
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    if (name === 'patient' && value) {
      const patient = patients.find(p => p.id.toString() === value)
      setPatientSpecies(patient?.species || null)
      setVitalParams(initVitalParams(patient?.species))
      setFormData(prev => ({ ...prev, patient: value }))
    } else {
      setFormData(prev => ({ ...prev, [name]: value }))
    }
  }

  const addService = () => {
    if (!serviceToAdd) return
    const service = services.find(s => s.id.toString() === serviceToAdd)
    if (service) {
      setSelectedServices(prev => [...prev, { id: service.id, name: service.name, price: service.price }])
      setServiceToAdd('')
    }
  }

  const removeService = (index) => {
    setSelectedServices(prev => prev.filter((_, i) => i !== index))
  }

  const addMedication = () => {
    if (!medicationToAdd) return
    const item = medicationItems.find(m => m.id.toString() === medicationToAdd)
    if (!item) return
    const qty = Math.max(1, Math.min(medicationQty, item.stock_on_hand))
    setSelectedMedications(prev => [...prev, { id: item.id, name: item.name, unit: item.unit, quantity: qty }])
    setMedicationToAdd('')
    setMedicationQty(1)
  }

  const removeMedication = (index) => {
    setSelectedMedications(prev => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    // Validate patient is selected
    if (!formData.patient) {
      setError(t('startVisit.selectPatientError'))
      setLoading(false)
      return
    }

    // Validate at least one service is added
    if (selectedServices.length === 0) {
      setError(t('startVisit.addServiceError'))
      setLoading(false)
      return
    }

    try {
      const patientId = parseInt(formData.patient, 10)
      
      // Combine vital params, visit notes, medication, and additional notes into a structured note
      // The API requires 'note' field to be present and non-empty
      const noteParts = []

      // Format vital parameters as structured text
      if (patientSpecies && VITAL_FIELD_CONFIGS[patientSpecies] && Object.keys(vitalParams).length > 0) {
        const vitalLines = []
        VITAL_FIELD_CONFIGS[patientSpecies].forEach(section => {
          vitalLines.push(`=== ${section.section} ===`)
          section.fields.forEach(f => {
            const val = vitalParams[f.key] ?? ''
            const unit = f.unit ? ` ${f.unit}` : ''
            vitalLines.push(`${f.label}: ${val}${unit}`)
          })
        })
        noteParts.push(vitalLines.join('\n'))
      }

      if (formData.visitNotes.trim()) {
        noteParts.push(`Notatki:\n${formData.visitNotes.trim()}`)
      }
      if (selectedMedications.length > 0) {
        const medLines = selectedMedications.map(m => `- ${m.name} x${m.quantity} ${m.unit}`)
        noteParts.push(`MEDICATION:\n${medLines.join('\n')}`)
      }
      if (formData.additionalNotes.trim()) {
        noteParts.push(`ADDITIONAL NOTES:\n${formData.additionalNotes.trim()}`)
      }
      
      const combinedNote = noteParts.join('\n\n')
      
      // Validate that at least one note field is filled (API requires 'note' field)
      if (!combinedNote.trim()) {
        setError(t('startVisit.fillSomeNotes'))
        setLoading(false)
        return
      }

      // Create history entry via patient history endpoint
      // According to PATIENT_VISIT_HISTORY_API.md:
      // - note: required
      // - receipt_summary: optional
      // - appointment: optional (must belong to same patient and clinic)
      const historyData = {
        note: combinedNote.trim(),
        receipt_summary: formData.medicalReceipts.trim() || '',
        ...(suggestedAppointment?.id && { appointment: suggestedAppointment.id }),
      }

      await patientHistoryAPI.create(patientId, historyData)

      // Record inventory movements for used medications
      const movementErrors = []
      for (const med of selectedMedications) {
        try {
          await inventoryAPI.recordMovement({
            item: med.id,
            kind: 'out',
            quantity: med.quantity,
            note: 'Used in visit',
            patient_id: patientId,
          })
        } catch (movErr) {
          console.error('Error recording inventory movement for', med.name, movErr)
          const detail = movErr.response?.data?.detail || movErr.response?.data?.quantity?.[0] || movErr.message
          movementErrors.push(`${med.name}: ${detail || 'unknown error'}`)
        }
      }

      // If services are added, create a draft invoice
      if (selectedServices.length > 0 && selectedOwner?.id) {
        const invoiceLines = selectedServices.map(s => ({
          description: s.name,
          quantity: 1,
          unit_price: String(s.price),
          service: s.id,
        }))
        try {
          await invoicesAPI.create({
            client: selectedOwner.id,
            patient: patientId,
            ...(suggestedAppointment?.id && { appointment: suggestedAppointment.id }),
            status: 'draft',
            lines: invoiceLines,
          })
        } catch (invErr) {
          console.error('Error creating invoice:', invErr)
          // Don't fail the whole operation; visit was saved
        }
      }

      // If there's a suggested appointment, update its status to "checked_in" or "completed"
      if (suggestedAppointment) {
        try {
          await appointmentsAPI.update(suggestedAppointment.id, {
            status: 'checked_in',
          })
        } catch (err) {
          console.error('Error updating appointment status:', err)
          // Don't fail the whole operation if status update fails
        }
      }

      if (movementErrors.length > 0) {
        // Visit was saved but some inventory movements failed — show warning then close
        setError(`${t('startVisit.saveSuccess')} ${t('startVisit.inventoryWarning')}: ${movementErrors.join('; ')}`)
        setLoading(false)
        setTimeout(() => { onSuccess(); onClose() }, 4000)
        return
      }

      onSuccess()
      onClose()

      // Reset form
      setFormData({
        patient: '',
        visitNotes: '',
        medicalReceipts: '',
        additionalNotes: '',
      })
      setVitalParams(initVitalParams('Dog'))
      setPatientSpecies('Dog')
      setSelectedServices([])
      setSelectedMedications([])
      setMedicationToAdd('')
      setMedicationQty(1)
      setOwnerSearch('')
      setSelectedOwner(null)
      setSuggestedAppointment(null)
    } catch (err) {
      // Handle API errors according to the API documentation
      let errorMessage = t('startVisit.saveError')
      
      if (err.response?.data) {
        // Handle validation errors from the API
        const errorData = err.response.data
        if (typeof errorData === 'string') {
          errorMessage = errorData
        } else if (errorData.detail) {
          errorMessage = errorData.detail
        } else if (errorData.note) {
          errorMessage = `Note: ${Array.isArray(errorData.note) ? errorData.note.join(', ') : errorData.note}`
        } else if (errorData.appointment) {
          errorMessage = `Appointment: ${Array.isArray(errorData.appointment) ? errorData.appointment.join(', ') : errorData.appointment}`
        } else if (typeof errorData === 'object') {
          // Try to extract first error message
          const firstError = Object.values(errorData)[0]
          errorMessage = Array.isArray(firstError) ? firstError[0] : firstError
        }
      } else if (err.message) {
        errorMessage = err.message
      }
      
      setError(errorMessage)
      console.error('Error saving visit:', err)
    } finally {
      setLoading(false)
    }
  }

  if (!standalone && !isOpen) return null

  return (
    <div
      className={standalone ? undefined : 'modal-overlay'}
      onClick={standalone ? undefined : onClose}
      style={standalone ? { padding: '1.5rem', maxWidth: '700px', margin: '0 auto' } : undefined}
    >
      <div
        className={standalone ? undefined : 'modal-content'}
        onClick={standalone ? undefined : (e) => e.stopPropagation()}
        style={standalone ? undefined : { maxWidth: '700px' }}
      >
        <div className="modal-header">
          <h2>{t('startVisit.title')}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          {suggestedAppointment && (
            <div style={{
              padding: '0.75rem',
              backgroundColor: '#e6f3ff',
              borderRadius: '6px',
              marginBottom: '1rem',
              fontSize: '0.9rem'
            }}>
              <strong>{t('startVisit.suggestedAppointment')}</strong> {suggestedAppointment.reason || t('startVisit.scheduledVisit')}
              <br />
              <span style={{ color: '#666', fontSize: '0.85rem' }}>
                {t('startVisit.modifyHint')}
              </span>
            </div>
          )}

          <div className="form-group" style={{ position: 'relative' }}>
            <label htmlFor="owner">{t('startVisit.owner')}</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                id="owner"
                name="owner_search_8374923"
                value={ownerSearch}
                onChange={handleOwnerSearchChange}
                placeholder={t('startVisit.ownerSearchPlaceholder')}
                autoComplete="new-password"
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  fontSize: '1rem',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                }}
                onFocus={() => {
                  if (ownerSearchResults.length > 0) {
                    setShowOwnerDropdown(true)
                  }
                }}
                onBlur={() => {
                  setTimeout(() => setShowOwnerDropdown(false), 200)
                }}
              />
              {searchingClients && (
                <div style={{
                  position: 'absolute',
                  right: '0.5rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  fontSize: '0.85rem',
                  color: '#718096'
                }}>
                  {t('common.searching')}
                </div>
              )}
              {showOwnerDropdown && ownerSearchResults.length > 0 && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  backgroundColor: 'white',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  marginTop: '0.25rem',
                  maxHeight: '200px',
                  overflowY: 'auto',
                  zIndex: 1000,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
                }}>
                  {ownerSearchResults.map(client => (
                    <div
                      key={client.id}
                      onClick={() => handleOwnerSelect(client)}
                      style={{
                        padding: '0.75rem',
                        cursor: 'pointer',
                        borderBottom: '1px solid #eee',
                        transition: 'background-color 0.2s'
                      }}
                      onMouseEnter={(e) => e.target.style.backgroundColor = '#f5f5f5'}
                      onMouseLeave={(e) => e.target.style.backgroundColor = 'white'}
                    >
                      <div style={{ fontWeight: '500' }}>
                        {client.first_name} {client.last_name}
                      </div>
                      {(client.email || client.phone) && (
                        <div style={{ fontSize: '0.85rem', color: '#718096', marginTop: '0.25rem' }}>
                          {client.email && <span>{client.email}</span>}
                          {client.email && client.phone && <span> • </span>}
                          {client.phone && <span>{client.phone}</span>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {ownerSearch.trim().length >= 2 && ownerSearchResults.length === 0 && !searchingClients && !selectedOwner && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#718096' }}>
                {t('startVisit.noOwnersFound')}
              </div>
            )}
            <div style={{ marginTop: '0.75rem' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowClientModal(true)}
                style={{ fontSize: '0.9rem', padding: '0.5rem 1rem' }}
              >
                {t('startVisit.createNewOwner')}
              </button>
            </div>
            {selectedOwner && (
              <div style={{
                marginTop: '0.5rem',
                padding: '0.5rem',
                backgroundColor: '#f0f9ff',
                borderRadius: '4px',
                fontSize: '0.9rem'
              }}>
                Selected: <strong>{selectedOwner.first_name} {selectedOwner.last_name}</strong>
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="patient">{t('startVisit.patient')}</label>
            {loadingPatients ? (
              <div className="loading-text">{t('patients.loadingPatients')}</div>
            ) : !selectedOwner ? (
              <div style={{ padding: '0.5rem', color: '#718096', fontSize: '0.9rem' }}>
                {t('startVisit.selectOwnerFirst')}
              </div>
            ) : patients.length === 0 ? (
              <div style={{ padding: '0.5rem', color: '#718096', fontSize: '0.9rem' }}>
                {t('startVisit.noPatientsForOwner')}
              </div>
            ) : (
              <select
                id="patient"
                name="patient"
                value={formData.patient}
                onChange={handleChange}
                required
              >
                <option value="">{t('startVisit.selectPatient')}</option>
                {patients.map((patient) => (
                  <option key={patient.id} value={patient.id}>
                    {patient.name} ({translateSpecies(patient.species, t)})
                  </option>
                ))}
              </select>
            )}
          </div>

          {patientSpecies && VITAL_FIELD_CONFIGS[patientSpecies] && (
            <div className="form-group">
              <label>{t('startVisit.vitalParams')}</label>
              {VITAL_FIELD_CONFIGS[patientSpecies].map(section => (
                <div key={section.section} style={{ marginBottom: '1rem' }}>
                  <div style={{
                    fontSize: '0.8rem',
                    fontWeight: '600',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: '#4a5568',
                    marginBottom: '0.5rem',
                    paddingBottom: '0.25rem',
                    borderBottom: '1px solid #e2e8f0',
                  }}>
                    {section.section}
                  </div>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                    gap: '0.5rem',
                  }}>
                    {section.fields.map(f => (
                      <div key={f.key} style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        <label htmlFor={`vital_${f.key}`} style={{ fontSize: '0.8rem', color: '#4a5568', fontWeight: '500' }}>
                          {f.label}{f.unit ? ` (${f.unit})` : ''}
                        </label>
                        <input
                          id={`vital_${f.key}`}
                          type="text"
                          value={vitalParams[f.key] ?? ''}
                          onChange={e => setVitalParams(prev => ({ ...prev, [f.key]: e.target.value }))}
                          style={{
                            padding: '0.35rem 0.5rem',
                            fontSize: '0.9rem',
                            border: '1px solid #ddd',
                            borderRadius: '4px',
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="form-group">
            <label htmlFor="visitNotes">{t('startVisit.visitNotes')}</label>
            <textarea
              id="visitNotes"
              name="visitNotes"
              value={formData.visitNotes}
              onChange={handleChange}
              rows="3"
              placeholder={t('startVisit.visitNotesPlaceholder')}
            />
          </div>

          <div className="form-group">
            <label>{t('startVisit.medication')}</label>
            {loadingMedications ? (
              <div className="loading-text">{t('startVisit.loadingMedications', { defaultValue: 'Loading medications...' })}</div>
            ) : medicationItems.length === 0 ? (
              <div style={{ fontSize: '0.9rem', color: '#718096' }}>
                {t('startVisit.noMedicationsInInventory', { defaultValue: 'No medications found in inventory.' })}
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <select
                    value={medicationToAdd}
                    onChange={e => setMedicationToAdd(e.target.value)}
                    style={{ flex: 1, padding: '0.5rem', fontSize: '1rem', border: '1px solid #ddd', borderRadius: '4px' }}
                  >
                    <option value="">{t('startVisit.chooseMedication', { defaultValue: 'Choose medication...' })}</option>
                    {medicationItems.map(m => (
                      <option key={m.id} value={m.id} disabled={m.stock_on_hand === 0}>
                        {m.name} — {t('inventory.stock', { defaultValue: 'stock' })}: {m.stock_on_hand} {m.unit}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min="1"
                    max={medicationItems.find(m => m.id.toString() === medicationToAdd)?.stock_on_hand || 99}
                    value={medicationQty}
                    onChange={e => setMedicationQty(Math.max(1, parseInt(e.target.value) || 1))}
                    style={{ width: '70px', padding: '0.5rem', fontSize: '1rem', border: '1px solid #ddd', borderRadius: '4px' }}
                  />
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={addMedication}
                    disabled={!medicationToAdd}
                    style={{ padding: '0.5rem 1rem' }}
                  >
                    {t('common.add')}
                  </button>
                </div>
                {selectedMedications.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                    {selectedMedications.map((m, index) => (
                      <div
                        key={`${m.id}-${index}`}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          padding: '0.5rem 0.75rem', backgroundColor: '#fef3c7', borderRadius: '4px', fontSize: '0.95rem',
                        }}
                      >
                        <span>{m.name} × {m.quantity} {m.unit}</span>
                        <button
                          type="button"
                          onClick={() => removeMedication(index)}
                          style={{ background: 'none', border: 'none', color: '#c53030', cursor: 'pointer', padding: '0.25rem', fontSize: '1.1rem', lineHeight: 1 }}
                        >×</button>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="medicalReceipts">{t('startVisit.medicalReceipts')}</label>
            <input
              type="text"
              id="medicalReceipts"
              name="medicalReceipts"
              value={formData.medicalReceipts}
              onChange={handleChange}
              placeholder={t('startVisit.medicalReceiptsPlaceholder')}
              maxLength={255}
            />
            <small style={{ color: '#666', fontSize: '0.85rem' }}>
              {t('startVisit.receiptHint')}
            </small>
          </div>

          <div className="form-group">
            <label htmlFor="additionalNotes">{t('startVisit.additionalNotes')}</label>
            <textarea
              id="additionalNotes"
              name="additionalNotes"
              value={formData.additionalNotes}
              onChange={handleChange}
              rows="3"
              placeholder={t('startVisit.additionalNotesPlaceholder')}
            />
          </div>

          <div
            className="form-group"
            style={{
              marginTop: '1.5rem',
              paddingTop: '1.5rem',
              borderTop: '1px solid #e2e8f0',
            }}
          >
            <label>{t('startVisit.services')}</label>
            <p style={{ fontSize: '0.85rem', color: '#718096', marginBottom: '0.75rem' }}>
              {t('startVisit.servicesHint')}
            </p>
            {loadingServices ? (
              <div className="loading-text">{t('startVisit.loadingServices')}</div>
            ) : servicesError ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontSize: '0.9rem', color: '#c53030' }}>{t('startVisit.servicesLoadError')}</span>
                <button
                  type="button"
                  onClick={() => setServicesFetchKey(k => k + 1)}
                  style={{
                    padding: '0.3rem 0.75rem',
                    fontSize: '0.85rem',
                    background: '#fff',
                    border: '1px solid #c53030',
                    borderRadius: '4px',
                    color: '#c53030',
                    cursor: 'pointer',
                  }}
                >
                  {t('common.retry')}
                </button>
              </div>
            ) : services.length === 0 ? (
              <div style={{ fontSize: '0.9rem', color: '#718096' }}>
                {t('startVisit.noServicesAvailable')}
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <select
                    value={serviceToAdd}
                    onChange={(e) => setServiceToAdd(e.target.value)}
                    style={{
                      flex: 1,
                      padding: '0.5rem',
                      fontSize: '1rem',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                    }}
                  >
                    <option value="">{t('startVisit.chooseService')}</option>
                    {services.map((service) => (
                      <option key={service.id} value={service.id}>
                        {service.name} – {service.price} PLN
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={addService}
                    disabled={!serviceToAdd}
                    style={{ padding: '0.5rem 1rem' }}
                  >
                    {t('common.add')}
                  </button>
                </div>
                {selectedServices.length > 0 && (
                  <>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem', marginBottom: '0.75rem' }}>
                      {selectedServices.map((s, index) => (
                        <div
                          key={`${s.id}-${index}`}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '0.5rem 0.75rem',
                            backgroundColor: '#e6fffa',
                            borderRadius: '4px',
                            fontSize: '0.95rem',
                          }}
                        >
                          <span>{s.name} – {s.price} PLN</span>
                          <button
                            type="button"
                            onClick={() => removeService(index)}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#c53030',
                              cursor: 'pointer',
                              padding: '0.25rem',
                              fontSize: '1.1rem',
                              lineHeight: 1,
                            }}
                            title="Remove"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                    <div
                      style={{
                        padding: '0.75rem 1rem',
                        backgroundColor: '#f7fafc',
                        borderRadius: '4px',
                        borderTop: '2px solid #2f855a',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontWeight: '600',
                        fontSize: '1.1rem',
                      }}
                    >
                      <span>{t('startVisit.visitBalance')}</span>
                      <span>
                        {selectedServices
                          .reduce((sum, s) => sum + parseFloat(s.price) || 0, 0)
                          .toFixed(2)}{' '}
                        PLN
                      </span>
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn-primary" disabled={loading || loadingServices}>
              {loading ? t('startVisit.saving') : t('startVisit.saveVisitDetails')}
            </button>
          </div>
        </form>
      </div>

      <AddClientModal
        isOpen={showClientModal}
        onClose={() => setShowClientModal(false)}
        onSuccess={(newClient) => {
          handleNewClientCreated(newClient)
        }}
      />
    </div>
  )
}

export default StartVisitModal

