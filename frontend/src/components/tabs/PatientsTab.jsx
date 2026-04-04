import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { patientsAPI } from "../../services/api";
import { translateSpecies } from "../../utils/species";
import AddPatientModal from "../modals/AddPatientModal";
import PatientDetailsModal from "../modals/PatientDetailsModal";
import SpeciesIcon from "../SpeciesIcon";
import "./Tabs.css";

const PatientsTab = ({ userRole = null }) => {
  const { t } = useTranslation();
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
  const abortControllerRef = React.useRef(null);

  const fetchPatients = async (search = "") => {
    // Cancel any in-flight request before starting a new one
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      setLoading(true);
      setError(null);
      const params = search ? { search } : {};
      const response = await patientsAPI.list(params, { signal: controller.signal });
      // Handle both paginated and non-paginated responses
      const patientsData = response.data.results || response.data || [];
      setPatients(Array.isArray(patientsData) ? patientsData : []);
    } catch (err) {
      if (err.name === "CanceledError" || err.code === "ERR_CANCELED") {
        return; // Ignore cancellations — a newer request is already in flight
      }
      console.error("Error fetching patients:", err);
      const errorMessage =
        err.response?.data?.detail ||
        err.message ||
        t("patients.loadError");
      setError(errorMessage);
      setPatients([]);
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchPatients();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleSearch = (e) => {
    const term = e.target.value;
    setSearchTerm(term);
    fetchPatients(term);
  };

  const calculateAge = (birthDate) => {
    if (!birthDate) return t("common.unknown");
    const today = new Date();
    const birth = new Date(birthDate);
    const years = today.getFullYear() - birth.getFullYear();
    const months = today.getMonth() - birth.getMonth();
    if (years > 0) {
      return `${years} ${years !== 1 ? t("patients.years") : t("patients.year")}`;
    }
    return `${months} ${months !== 1 ? t("patients.months") : t("patients.month")}`;
  };

  return (
    <div className="tab-container">
      <div className="tab-header">
        <button className="btn-primary" onClick={() => setIsModalOpen(true)}>
          {t("patients.addPatient")}
        </button>
      </div>

      <div className="tab-content-wrapper">
        <div className="search-bar">
          <input
            type="text"
            placeholder={t("patients.searchPlaceholder")}
            className="search-input"
            value={searchTerm}
            onChange={handleSearch}
          />
        </div>

        {loading && <div className="loading-message">{t("patients.loadingPatients")}</div>}

        {error && !loading && (
          <div
            style={{
              padding: "1rem",
              backgroundColor: "#fff5f5",
              borderRadius: "8px",
              border: "1px solid #fed7d7",
              color: "#c53030",
              marginBottom: "1rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "1rem",
            }}
          >
            <span>{error}</span>
            <button
              className="btn-secondary"
              onClick={() => fetchPatients(searchTerm)}
            >
              {t("common.retry")}
            </button>
          </div>
        )}

        {!loading && patients.length === 0 ? (
          <div className="empty-state">{t("patients.noPatientsFound")}</div>
        ) : (
          <div className="patients-list">
            {patients.map((patient) => (
              <button
                key={patient.id}
                className="patient-row"
                onClick={() => {
                  setSelectedPatient(patient);
                  setIsDetailsModalOpen(true);
                }}
              >
                <SpeciesIcon species={patient.species} size={28} color="#16a34a" />
                <span className="patient-row-name">{patient.name}</span>
                <span className="patient-row-species">
                  {translateSpecies(patient.species, t)}
                  {patient.breed ? ` · ${patient.breed}` : ""}
                </span>
                <span className="patient-row-owner">
                  {patient.owner
                    ? `${patient.owner.first_name} ${patient.owner.last_name}`
                    : "—"}
                </span>
                <span className="patient-row-age">{calculateAge(patient.birth_date)}</span>
                <span className="patient-row-arrow">›</span>
              </button>
            ))}
          </div>
        )}
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
        userRole={userRole}
      />
    </div>
  );
};

export default PatientsTab;
