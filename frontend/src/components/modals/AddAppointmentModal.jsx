import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  appointmentsAPI,
  patientsAPI,
  authAPI,
  vetsAPI,
  clientsAPI,
  availabilityAPI,
  roomsAPI,
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

import { translateSpecies } from "../../utils/species";

const REASON_OPTIONS = [
  { value: "Routine Checkup", key: "reasonRoutineCheckup" },
  { value: "Vaccination", key: "reasonVaccination" },
  { value: "Surgery", key: "reasonSurgery" },
  { value: "Dental Cleaning", key: "reasonDentalCleaning" },
  { value: "Emergency", key: "reasonEmergency" },
  { value: "Follow-up", key: "reasonFollowUp" },
  { value: "Grooming", key: "reasonGrooming" },
  { value: "Behavior Consultation", key: "reasonBehaviorConsultation" },
  { value: "Other", key: "reasonOther" },
];

const AddAppointmentModal = ({ isOpen, onClose, onSuccess, initialStartsAt }) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState({
    patient: "",
    vet: "",
    room: "",
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
  const [rooms, setRooms] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchingClients, setSearchingClients] = useState(false);
  const [error, setError] = useState(null);
  const [showClientModal, setShowClientModal] = useState(false);
  const [availability, setAvailability] = useState(null);
  const [loadingAvailability, setLoadingAvailability] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    // Reset form when modal opens
    setFormData({
      patient: "",
      vet: "",
      room: "",
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
        const [vetsRes, userRes, roomsRes] = await Promise.all([
          vetsAPI.list(),
          authAPI.me(),
          roomsAPI.list(),
        ]);
        setVets(vetsRes.data.results || vetsRes.data);
        setRooms(roomsRes.data.results || roomsRes.data || []);
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

    let startTime;
    if (initialStartsAt) {
      startTime = initialStartsAt;
    } else {
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const nextHour = new Date(today);
      nextHour.setHours(now.getHours() + 1, 0, 0, 0);
      if (nextHour.getDate() !== today.getDate()) {
        nextHour.setTime(today.getTime());
        nextHour.setHours(8, 0, 0, 0);
      }
      startTime = formatDateTimeLocal(nextHour);
    }
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

  // Fetch availability when vet and date are selected
  useEffect(() => {
    const fetchAvailability = async () => {
      if (!formData.vet || !formData.starts_at) {
        setAvailability(null);
        return;
      }

      try {
        setLoadingAvailability(true);
        const selectedDate = new Date(formData.starts_at);
        const dateStr = selectedDate.toISOString().split('T')[0]; // YYYY-MM-DD format
        
        const response = await availabilityAPI.get({
          date: dateStr,
          vet: formData.vet,
          slot_minutes: 30,
        });
        setAvailability(response.data);
      } catch (err) {
        console.error("Error fetching availability:", err);
        setAvailability(null);
      } finally {
        setLoadingAvailability(false);
      }
    };

    fetchAvailability();
  }, [formData.vet, formData.starts_at ? formData.starts_at.split('T')[0] : null]); // Only refetch when date changes, not time

  const isTimeAvailable = (dateTimeString) => {
    if (!availability || !availability.free || availability.free.length === 0) {
      return false;
    }

    const selectedTime = new Date(dateTimeString);
    const selectedEnd = new Date(selectedTime.getTime() + 30 * 60 * 1000); // 30 min duration

    // Check if the selected time falls within any free slot
    return availability.free.some((slot) => {
      const slotStart = new Date(slot.start);
      const slotEnd = new Date(slot.end);
      // Time is available if it starts at or after slot start and ends at or before slot end
      return selectedTime >= slotStart && selectedEnd <= slotEnd;
    });
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
      
      // If vet changes, clear availability
      if (name === "vet") {
        setAvailability(null);
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

  const getReasonDisplayText = (reasonValue) => {
    if (reasonValue === "Other") return formData.reasonCustom || "";
    const opt = REASON_OPTIONS.find((r) => r.value === reasonValue);
    return opt ? t(`addAppointment.${opt.key}`) : reasonValue;
  };

  const getFormattedReasonDisplay = () => {
    const selectedPatient = patients.find(p => p.id === parseInt(formData.patient));
    const patientName = selectedPatient?.name || "";
    const reasonText = getReasonDisplayText(formData.reason);
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
      setError(t("addAppointment.selectOwnerError"));
      setLoading(false);
      return;
    }

    if (!formData.patient) {
      setError(t("addAppointment.selectPatientError"));
      setLoading(false);
      return;
    }

    if (!formData.reason) {
      setError(t("addAppointment.selectReasonError"));
      setLoading(false);
      return;
    }

    if (formData.reason === "Other" && !formData.reasonCustom.trim()) {
      setError(t("addAppointment.customReasonError"));
      setLoading(false);
      return;
    }

    // Validate that the selected time is not in the past
    if (formData.starts_at) {
      const selectedStartTime = new Date(formData.starts_at);
      const now = new Date();
      if (selectedStartTime < now) {
        setError(t("addAppointment.pastTimeError"));
        setLoading(false);
        return;
      }
    }

    // Validate that the selected time is available
    if (formData.vet && formData.starts_at && availability) {
      if (!isTimeAvailable(formData.starts_at)) {
        setError(t("addAppointment.timeNotAvailableError"));
        setLoading(false);
        return;
      }
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
        room: formData.room ? parseInt(formData.room, 10) : null,
      };

      // Remove reasonCustom from data (it's not part of the API)
      delete appointmentData.reasonCustom;
      
      await appointmentsAPI.create(appointmentData);
      onSuccess();
      onClose();
    } catch (err) {
      let errorMessage = t("addAppointment.createError");
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
          <h2>{t("addAppointment.title")}</h2>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-group" style={{ position: 'relative' }}>
            <label htmlFor="owner">{t("addAppointment.owner")}</label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                id="owner"
                name="owner_search_8374923"
                value={ownerSearch}
                onChange={handleOwnerSearchChange}
                placeholder={t("addAppointment.ownerSearchPlaceholder")}
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
                  {t("common.searching")}
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
                {t("addAppointment.noOwnersFound")}
              </div>
            )}
            <div style={{ marginTop: '0.75rem' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowClientModal(true)}
                style={{ fontSize: '0.9rem', padding: '0.5rem 1rem' }}
              >
                {t("addAppointment.createNewOwner")}
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
                {t("addAppointment.selectedLabel")} <strong>{selectedOwner.first_name} {selectedOwner.last_name}</strong>
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="patient">{t("addAppointment.patient")}</label>
            {loadingPatients ? (
              <div className="loading-text">{t("patients.loadingPatients")}</div>
            ) : !selectedOwner ? (
              <div style={{ padding: '0.5rem', color: '#718096', fontSize: '0.9rem' }}>
                {t("addAppointment.selectOwnerFirst")}
              </div>
            ) : patients.length === 0 ? (
              <div style={{ padding: '0.5rem', color: '#718096', fontSize: '0.9rem' }}>
                {t("addAppointment.noPatientsForOwner")}
              </div>
            ) : (
              <select
                id="patient"
                name="patient"
                value={formData.patient}
                onChange={handleChange}
                required
              >
                <option value="">{t("addAppointment.selectPatient")}</option>
                {patients.map((patient) => (
                  <option key={patient.id} value={patient.id}>
                    {patient.name} ({translateSpecies(patient.species, t)})
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="vet">{t("addAppointment.vet")}</label>
            <select
              id="vet"
              name="vet"
              value={formData.vet}
              onChange={handleChange}
              required
            >
              <option value="">{t("addAppointment.selectVet")}</option>
              {vets.map((vet) => (
                <option key={vet.id} value={vet.id}>
                  {vet.first_name && vet.last_name
                    ? `${vet.first_name} ${vet.last_name}`
                    : vet.username}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="room">{t("addAppointment.room")}</label>
            <select
              id="room"
              name="room"
              value={formData.room}
              onChange={handleChange}
            >
              <option value="">{t("addAppointment.noRoom")}</option>
              {rooms.map((room) => (
                <option key={room.id} value={room.id}>
                  {t('rooms.' + room.name, { defaultValue: room.name })}
                </option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="starts_at">{t("addAppointment.startTime")}</label>
              <input
                type="datetime-local"
                id="starts_at"
                name="starts_at"
                value={formData.starts_at}
                onChange={handleChange}
                required
                min={formatDateTimeLocal(new Date())}
                style={{
                  borderColor: (() => {
                    if (!formData.starts_at) return undefined;
                    const selectedTime = new Date(formData.starts_at);
                    const now = new Date();
                    if (selectedTime < now) {
                      return '#ef4444'; // Red border if in the past
                    }
                    if (formData.vet && availability && !isTimeAvailable(formData.starts_at)) {
                      return '#ef4444'; // Red border if not available
                    }
                    return undefined;
                  })()
                }}
              />
              {formData.starts_at && (() => {
                const selectedTime = new Date(formData.starts_at);
                const now = new Date();
                if (selectedTime < now) {
                  return (
                    <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                      <span style={{ color: '#ef4444' }}>✗ {t("addAppointment.cannotScheduleInPast")}</span>
                    </div>
                  );
                }
                return null;
              })()}
              {loadingAvailability && (
                <div style={{ fontSize: '0.85rem', color: '#718096', marginTop: '0.25rem' }}>
                  {t("addAppointment.loadingAvailability")}
                </div>
              )}
              {formData.vet && formData.starts_at && availability && (() => {
                const selectedTime = new Date(formData.starts_at);
                const now = new Date();
                if (selectedTime < now) return null; // Don't show availability check if in past
                
                return (
                  <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                    {isTimeAvailable(formData.starts_at) ? (
                      <span style={{ color: '#10b981' }}>✓ {t("addAppointment.timeSlotAvailable")}</span>
                    ) : (
                      <span style={{ color: '#ef4444' }}>
                        ✗ {t("addAppointment.timeSlotNotAvailable")} {availability.free && availability.free.length > 0 
                          ? t("addAppointment.selectAvailableTime")
                          : availability.closed_reason || t("addAppointment.noAvailableSlots")}
                      </span>
                    )}
                  </div>
                );
              })()}
            </div>
            <div className="form-group">
              <label htmlFor="ends_at">{t("addAppointment.endTime")}</label>
              <input
                type="datetime-local"
                id="ends_at"
                name="ends_at"
                value={formData.ends_at}
                onChange={handleChange}
                readOnly
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="reason">{t("addAppointment.reasonForVisit")}</label>
            <select
              id="reason"
              name="reason"
              value={formData.reason}
              onChange={handleChange}
              required
            >
              <option value="">{t("addAppointment.selectReason")}</option>
              {REASON_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {t(`addAppointment.${r.key}`)}
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
                placeholder={t("addAppointment.customReasonPlaceholder")}
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
                {t("addAppointment.visitWillBeSavedAs")} <strong>{getFormattedReasonDisplay()}</strong>
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="status">{t("addAppointment.status")}</label>
            <select
              id="status"
              name="status"
              value={formData.status}
              onChange={handleChange}
            >
              <option value="scheduled">{t("addAppointment.statusScheduled")}</option>
              <option value="confirmed">{t("addAppointment.statusConfirmed")}</option>
              <option value="checked_in">{t("addAppointment.statusCheckedIn")}</option>
              <option value="completed">{t("addAppointment.statusCompleted")}</option>
            </select>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              {t("common.cancel")}
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? t("addAppointment.scheduling") : t("addAppointment.scheduleVisit")}
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
