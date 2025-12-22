import React, { useState, useEffect } from 'react'
import { patientsAPI } from '../../services/api'
import AddPatientModal from '../modals/AddPatientModal'
import './Tabs.css'

// Placeholder data
const placeholderPatients = [
  {
    id: 1,
    name: 'Max',
    species: 'Dog',
    breed: 'Golden Retriever',
    owner: { first_name: 'John', last_name: 'Doe' },
    birth_date: '2019-01-15',
  },
  {
    id: 2,
    name: 'Luna',
    species: 'Cat',
    breed: 'Persian',
    owner: { first_name: 'Jane', last_name: 'Smith' },
    birth_date: '2021-03-20',
  },
  {
    id: 3,
    name: 'Bunny',
    species: 'Rabbit',
    breed: 'Dutch',
    owner: { first_name: 'Mike', last_name: 'Johnson' },
    birth_date: '2022-06-10',
  },
]

const PatientsTab = () => {
  const [patients, setPatients] = useState(placeholderPatients)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [useAPI, setUseAPI] = useState(true)
  const [isModalOpen, setIsModalOpen] = useState(false)

  const fetchPatients = async (search = '') => {
    if (!useAPI) {
      // Filter placeholder data
      const filtered = search
        ? placeholderPatients.filter(p => 
            p.name.toLowerCase().includes(search.toLowerCase()) ||
            p.species.toLowerCase().includes(search.toLowerCase()) ||
            `${p.owner.first_name} ${p.owner.last_name}`.toLowerCase().includes(search.toLowerCase())
          )
        : placeholderPatients
      setPatients(filtered)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const params = search ? { search } : {}
      const response = await patientsAPI.list(params)
      setPatients(response.data.results || response.data)
    } catch (err) {
      // Fall back to placeholder data on error
      setUseAPI(false)
      const filtered = search
        ? placeholderPatients.filter(p => 
            p.name.toLowerCase().includes(search.toLowerCase()) ||
            p.species.toLowerCase().includes(search.toLowerCase()) ||
            `${p.owner.first_name} ${p.owner.last_name}`.toLowerCase().includes(search.toLowerCase())
          )
        : placeholderPatients
      setPatients(filtered)
      console.error('Error fetching patients, using placeholder data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPatients()
  }, [])

  const handleSearch = (e) => {
    const term = e.target.value
    setSearchTerm(term)
    fetchPatients(term)
  }

  const getSpeciesEmoji = (species) => {
    const speciesLower = species?.toLowerCase() || ''
    if (speciesLower.includes('dog')) return '🐕'
    if (speciesLower.includes('cat')) return '🐱'
    if (speciesLower.includes('rabbit')) return '🐰'
    if (speciesLower.includes('bird')) return '🐦'
    if (speciesLower.includes('hamster')) return '🐹'
    return '🐾'
  }

  const calculateAge = (birthDate) => {
    if (!birthDate) return 'Unknown'
    const today = new Date()
    const birth = new Date(birthDate)
    const years = today.getFullYear() - birth.getFullYear()
    const months = today.getMonth() - birth.getMonth()
    if (years > 0) {
      return `${years} year${years !== 1 ? 's' : ''}`
    }
    return `${months} month${months !== 1 ? 's' : ''}`
  }

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>Patients</h2>
        <button className="btn-primary" onClick={() => setIsModalOpen(true)}>
          + Add Patient
        </button>
      </div>
      
      <div className="tab-content-wrapper">
        <div className="search-bar">
          <input 
            type="text" 
            placeholder="Search patients by name, owner, or ID..." 
            className="search-input"
            value={searchTerm}
            onChange={handleSearch}
          />
        </div>

        {loading && <div className="loading-message">Loading patients...</div>}
        
        <div className="patients-grid">
          {patients.length === 0 ? (
            <div className="empty-state">No patients found</div>
          ) : (
            patients.map((patient) => (
                <div key={patient.id} className="patient-card">
                  <div className="patient-card-header">
                    <div className="patient-avatar">{getSpeciesEmoji(patient.species)}</div>
                    <div className="patient-name-section">
                      <h3>{patient.name}</h3>
                      <p className="patient-species">
                        {patient.species} {patient.breed ? `• ${patient.breed}` : ''}
                      </p>
                    </div>
                  </div>
                  <div className="patient-details">
                    <div className="patient-detail-row">
                      <span className="detail-label">Owner:</span>
                      <span className="detail-value">
                        {patient.owner ? `${patient.owner.first_name} ${patient.owner.last_name}` : 'Unknown'}
                      </span>
                    </div>
                    <div className="patient-detail-row">
                      <span className="detail-label">Age:</span>
                      <span className="detail-value">{calculateAge(patient.birth_date)}</span>
                    </div>
                  </div>
                  <div className="patient-actions">
                    <button className="btn-secondary">View Details</button>
                  </div>
                </div>
            ))
          )}
        </div>
      </div>

      <AddPatientModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => {
          fetchPatients(searchTerm)
          setUseAPI(true)
        }}
      />
    </div>
  )
}

export default PatientsTab

