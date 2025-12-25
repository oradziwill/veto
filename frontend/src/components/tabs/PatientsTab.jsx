import React, { useState, useEffect } from "react";
import { patientsAPI } from "../../services/api";
import AddPatientModal from "../modals/AddPatientModal";
import PatientDetailsModal from "../modals/PatientDetailsModal";
import "./Tabs.css";

const PatientsTab = () => {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);

  const fetchPatients = async (search = "") => {
    try {
      setLoading(true);
      setError(null);
      const params = search ? { search } : {};
      const response = await patientsAPI.list(params);
      // Handle both paginated and non-paginated responses
      const patientsData = response.data.results || response.data || [];
      setPatients(Array.isArray(patientsData) ? patientsData : []);
    } catch (err) {
      console.error("Error fetching patients:", err);
      setError("Failed to load patients. Please try again.");
      setPatients([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPatients();
  }, []);

  const handleSearch = (e) => {
    const term = e.target.value;
    setSearchTerm(term);
    fetchPatients(term);
  };

  const getSpeciesEmoji = (species) => {
    const speciesLower = species?.toLowerCase() || "";
    if (speciesLower.includes("dog")) return "🐕";
    if (speciesLower.includes("cat")) return "🐱";
    if (speciesLower.includes("rabbit")) return "🐰";
    if (speciesLower.includes("bird")) return "🐦";
    if (speciesLower.includes("hamster")) return "🐹";
    return "🐾";
  };

  const calculateAge = (birthDate) => {
    if (!birthDate) return "Unknown";
    const today = new Date();
    const birth = new Date(birthDate);
    const years = today.getFullYear() - birth.getFullYear();
    const months = today.getMonth() - birth.getMonth();
    if (years > 0) {
      return `${years} year${years !== 1 ? "s" : ""}`;
    }
    return `${months} month${months !== 1 ? "s" : ""}`;
  };

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
            placeholder="Search by patient name, owner name, surname, or phone..."
            className="search-input"
            value={searchTerm}
            onChange={handleSearch}
          />
        </div>

        {loading && <div className="loading-message">Loading patients...</div>}

        {error && !loading && (
          <div
            className="error-message"
            style={{
              padding: "1rem",
              backgroundColor: "#fff5f5",
              borderRadius: "8px",
              border: "1px solid #fed7d7",
              color: "#c53030",
              marginBottom: "1rem",
            }}
          >
            {error}
          </div>
        )}

        <div className="patients-grid">
          {!loading && patients.length === 0 ? (
            <div className="empty-state">No patients found</div>
          ) : (
            patients.map((patient) => (
              <div key={patient.id} className="patient-card">
                <div className="patient-card-header">
                  <div className="patient-avatar">
                    {getSpeciesEmoji(patient.species)}
                  </div>
                  <div className="patient-name-section">
                    <h3>{patient.name}</h3>
                    <p className="patient-species">
                      {patient.species}{" "}
                      {patient.breed ? `• ${patient.breed}` : ""}
                    </p>
                  </div>
                </div>
                <div className="patient-details">
                  <div className="patient-detail-row">
                    <span className="detail-label">Owner:</span>
                    <span className="detail-value">
                      {patient.owner
                        ? `${patient.owner.first_name} ${patient.owner.last_name}`
                        : "Unknown"}
                    </span>
                  </div>
                  <div className="patient-detail-row">
                    <span className="detail-label">Age:</span>
                    <span className="detail-value">
                      {calculateAge(patient.birth_date)}
                    </span>
                  </div>
                </div>
                <div className="patient-actions">
                  <button
                    className="btn-secondary"
                    onClick={() => {
                      setSelectedPatient(patient);
                      setIsDetailsModalOpen(true);
                    }}
                  >
                    View Details
                  </button>
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
          fetchPatients(searchTerm);
        }}
      />

      <PatientDetailsModal
        isOpen={isDetailsModalOpen}
        onClose={() => {
          setIsDetailsModalOpen(false);
          setSelectedPatient(null);
        }}
        patient={selectedPatient}
      />
    </div>
  );
};

export default PatientsTab;
