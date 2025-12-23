import React, { useState, useEffect } from "react";
import {
  appointmentsAPI,
  patientsAPI,
  authAPI,
  vetsAPI,
  clientsAPI,
} from "../../services/api";
import AddClientModal from "./AddClientModal";
import "./Modal.css";

const formatDateTimeLocal = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

const add30Minutes = (datetimeLocalString) => {
  const date = new Date(datetimeLocalString);
  date.setMinutes(date.getMinutes() + 30);
  return formatDateTimeLocal(date);
};

const REASON_OPTIONS = [
  "Routine Checkup",
  "Vaccination",
  "Surgery",
  "Dental Cleaning",
  "Emergency",
  "Follow-up",
  "Grooming",
  "Behavior Consultation",
  "Other",
];

const AddAppointmentModal = ({ isOpen, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    patient: "",
    vet: "",
    starts_at: "",
    ends_at: "",
    reason: "",
    reasonCustom: "",
    status: "scheduled",
  });
  const [ownerSearch, setOwnerSearch] = useState("");
  const [ownerSearchResults, setOwnerSearchResults] = useState([]);
  const [selectedOwner, setSelectedOwner] = useState(null);
  const [showOwnerDropdown, setShowOwnerDropdown] = useState(false);
  const [patients, setPatients] = useState([]);
  const [loadingPatients, setLoadingPatients] = useState(false);
  const [vets, setVets] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchingClients, setSearchingClients] = useState(false);
  const [error, setError] = useState(null);
  const [showClientModal, setShowClientModal] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    // Reset form when modal opens
    setFormData({
      patient: "",
      vet: "",
      starts_at: "",
      ends_at: "",
      reason: "",
      reasonCustom: "",
      status: "scheduled",
    });
    setOwnerSearch("");
    setSelectedOwner(null);
    setOwnerSearchResults([]);
    setShowOwnerDropdown(false);
    setPatients([]);

    const loadData = async () => {
      try {
        const [vetsRes, userRes] = await Promise.all([
          vetsAPI.list(),
          authAPI.me(),
        ]);
        setVets(vetsRes.data.results || vetsRes.data);
        const user = userRes.data;
        setCurrentUser(user);
        if (user.id) {
          setFormData((prev) => ({ ...prev, vet: user.id.toString() }));
        }
      } catch (err) {
        console.error("Error loading data:", err);
      }
    };

    loadData();

    const now = new Date();
    const nextHour = new Date(now.getTime() + 60 * 60 * 1000);
    nextHour.setMinutes(0, 0, 0);
    const startTime = formatDateTimeLocal(nextHour);
    setFormData((prev) => ({
      ...prev,
      starts_at: startTime,
      ends_at: add30Minutes(startTime),
    }));
  }, [isOpen]);

  // Search for clients when ownerSearch changes
  useEffect(() => {
    const searchClients = async () => {
      if (ownerSearch.trim().length < 2) {
        setOwnerSearchResults([]);
        setShowOwnerDropdown(false);
        return;
      }

      try {
        setSearchingClients(true);
        const response = await clientsAPI.list({ search: ownerSearch.trim() });
        const results = response.data.results || response.data;
        setOwnerSearchResults(results);
        setShowOwnerDropdown(results.length > 0);
      } catch (err) {
        console.error("Error searching clients:", err);
        setOwnerSearchResults([]);
        setShowOwnerDropdown(false);
      } finally {
        setSearchingClients(false);
      }
    };

    const timeoutId = setTimeout(searchClients, 300); // Debounce search
    return () => clearTimeout(timeoutId);
  }, [ownerSearch]);

  // Load patients when owner is selected
  useEffect(() => {
    const loadPatients = async () => {
      if (!selectedOwner?.id) {
        setPatients([]);
        return;
      }

      try {
        setLoadingPatients(true);
        const response = await patientsAPI.list({ owner: selectedOwner.id });
        const patientsData = response.data.results || response.data;
        setPatients(patientsData);
      } catch (err) {
        console.error("Error loading patients:", err);
        setPatients([]);
      } finally {
        setLoadingPatients(false);
      }
    };

    loadPatients();
  }, [selectedOwner]);

  const handleOwnerSearchChange = (e) => {
    const value = e.target.value;
    setOwnerSearch(value);
    if (!value) {
      setSelectedOwner(null);
      setFormData((prev) => ({ ...prev, patient: "" }));
      setPatients([]);
      setShowOwnerDropdown(false);
    }
  };

  const handleOwnerSelect = (client) => {
    setSelectedOwner(client);
    setOwnerSearch(`${client.first_name} ${client.last_name}`);
    setFormData((prev) => ({ ...prev, patient: "" })); // Clear patient when owner changes
    setShowOwnerDropdown(false);
    setOwnerSearchResults([]);
  };

  const handleNewClientCreated = (newClient) => {
    setSelectedOwner(newClient);
    setOwnerSearch(`${newClient.first_name} ${newClient.last_name}`);
    setShowClientModal(false);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => {
      const updated = { ...prev, [name]: value };
      
      if (name === "starts_at" && value) {
        updated.ends_at = add30Minutes(value);
      }
      
      // If reason changes, clear custom reason if not "Other"
      if (name === "reason" && value !== "Other") {
        updated.reasonCustom = "";
      }
      
      return updated;
    });
  };

  const getFormattedReason = () => {
    const selectedPatient = patients.find(p => p.id === parseInt(formData.patient));
    const patientName = selectedPatient?.name || "";
    
    let reasonText = formData.reason === "Other" 
      ? formData.reasonCustom 
      : formData.reason;
    
    // Only include patient name if it exists and is not "Unknown"
    if (patientName && patientName.trim() && patientName.trim() !== "Unknown" && reasonText) {
      return `${patientName} - ${reasonText}`;
    }
    return reasonText;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Validate owner and patient are selected
    if (!selectedOwner) {
      setError("Please select an owner for this visit.");
      setLoading(false);
      return;
    }

    if (!formData.patient) {
      setError("Please select a patient for this visit.");
      setLoading(false);
      return;
    }

    if (!formData.reason) {
      setError("Please select a reason for this visit.");
      setLoading(false);
      return;
    }

    if (formData.reason === "Other" && !formData.reasonCustom.trim()) {
      setError("Please enter a custom reason.");
      setLoading(false);
      return;
    }

    try {
      const formattedReason = getFormattedReason();
      const appointmentData = {
        ...formData,
        reason: formattedReason,
        starts_at: new Date(formData.starts_at).toISOString(),
        ends_at: new Date(formData.ends_at).toISOString(),
        patient: parseInt(formData.patient),
        vet: parseInt(formData.vet) || currentUser?.id || null,
      };
      
      // Remove reasonCustom from data (it's not part of the API)
      delete appointmentData.reasonCustom;
      
      await appointmentsAPI.create(appointmentData);
      onSuccess();
      onClose();
    } catch (err) {
      let errorMessage = "Failed to create appointment. Please try again.";
      if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (typeof err.response?.data === "object") {
        const errors = Object.entries(err.response.data)
          .map(([field, messages]) => {
            const fieldLabel = field
              .replace(/_/g, " ")
              .replace(/\b\w/g, (l) => l.toUpperCase());
            const msg = Array.isArray(messages)
              ? messages.join(", ")
              : String(messages);
            return `${fieldLabel}: ${msg}`;
          })
          .join("; ");
        errorMessage = errors || errorMessage;
      }
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Schedule New Visit</h2>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-group" style={{ position: 'relative' }}>
            <label htmlFor="owner">Owner *</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                id="owner"
                name="owner"
                value={ownerSearch}
                onChange={handleOwnerSearchChange}
                placeholder="Search for owner by name, phone, or email..."
                style={{ 
                  width: '100%',
                  padding: '0.5rem',
                  fontSize: '1rem',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                }}
                onFocus={() => {
                  if (ownerSearchResults.length > 0) {
                    setShowOwnerDropdown(true);
                  }
                }}
                onBlur={() => {
                  setTimeout(() => setShowOwnerDropdown(false), 200);
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
                  Searching...
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
            {ownerSearch.trim().length >= 2 && ownerSearchResults.length === 0 && !searchingClients && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#718096' }}>
                No owners found. Create a new one below.
              </div>
            )}
            <div style={{ marginTop: '0.75rem' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowClientModal(true)}
                style={{ fontSize: '0.9rem', padding: '0.5rem 1rem' }}
              >
                + Create New Owner
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
            <label htmlFor="patient">Patient *</label>
            {loadingPatients ? (
              <div className="loading-text">Loading patients...</div>
            ) : !selectedOwner ? (
              <div style={{ padding: '0.5rem', color: '#718096', fontSize: '0.9rem' }}>
                Please select an owner first
              </div>
            ) : patients.length === 0 ? (
              <div style={{ padding: '0.5rem', color: '#718096', fontSize: '0.9rem' }}>
                No patients found for this owner
              </div>
            ) : (
              <select
                id="patient"
                name="patient"
                value={formData.patient}
                onChange={handleChange}
                required
              >
                <option value="">Select Patient</option>
                {patients.map((patient) => (
                  <option key={patient.id} value={patient.id}>
                    {patient.name} ({patient.species})
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="vet">Veterinarian *</label>
            <select
              id="vet"
              name="vet"
              value={formData.vet}
              onChange={handleChange}
              required
            >
              <option value="">Select Veterinarian</option>
              {vets.map((vet) => (
                <option key={vet.id} value={vet.id}>
                  {vet.first_name && vet.last_name
                    ? `${vet.first_name} ${vet.last_name}`
                    : vet.username}
                </option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="starts_at">Start Time *</label>
              <input
                type="datetime-local"
                id="starts_at"
                name="starts_at"
                value={formData.starts_at}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="ends_at">End Time *</label>
              <input
                type="datetime-local"
                id="ends_at"
                name="ends_at"
                value={formData.ends_at}
                readOnly
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="reason">Reason for Visit *</label>
            <select
              id="reason"
              name="reason"
              value={formData.reason}
              onChange={handleChange}
              required
            >
              <option value="">Select Reason</option>
              {REASON_OPTIONS.map((reason) => (
                <option key={reason} value={reason}>
                  {reason}
                </option>
              ))}
            </select>
            {formData.reason === "Other" && (
              <input
                type="text"
                id="reasonCustom"
                name="reasonCustom"
                value={formData.reasonCustom}
                onChange={handleChange}
                placeholder="Enter custom reason..."
                required
                style={{ marginTop: '0.5rem', width: '100%', padding: '0.5rem' }}
              />
            )}
            {formData.reason && formData.patient && (
              <div style={{ 
                marginTop: '0.5rem', 
                padding: '0.5rem', 
                backgroundColor: '#f0f9ff', 
                borderRadius: '4px',
                fontSize: '0.85rem',
                color: '#374151'
              }}>
                Visit will be saved as: <strong>{getFormattedReason()}</strong>
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="status">Status</label>
            <select
              id="status"
              name="status"
              value={formData.status}
              onChange={handleChange}
            >
              <option value="scheduled">Scheduled</option>
              <option value="confirmed">Confirmed</option>
              <option value="checked_in">Checked-in</option>
              <option value="completed">Completed</option>
            </select>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Scheduling..." : "Schedule Visit"}
            </button>
          </div>
        </form>
      </div>

      <AddClientModal
        isOpen={showClientModal}
        onClose={() => setShowClientModal(false)}
        onSuccess={(newClient) => {
          handleNewClientCreated(newClient);
        }}
      />
    </div>
  );
};

export default AddAppointmentModal;
