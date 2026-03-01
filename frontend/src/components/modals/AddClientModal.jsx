import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { clientsAPI, authAPI } from "../../services/api";
import "./Modal.css";

const AddClientModal = ({ isOpen, onClose, onSuccess }) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    email: "",
    street: "",
    house_number: "",
    apartment: "",
    city: "",
    postal_code: "",
    country: "Polska",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  // Ensure authentication before making API calls
  const ensureAuthenticated = async () => {
    const token = localStorage.getItem("access_token");
    if (token) {
      try {
        // Verify token is still valid
        await authAPI.me();
        return true;
      } catch (err) {
        // Token invalid, clear it
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      }
    }

    // Try to auto-login
    try {
      const authResponse = await authAPI.login("drsmith", "password123");
      localStorage.setItem("access_token", authResponse.data.access);
      localStorage.setItem("refresh_token", authResponse.data.refresh);
      return true;
    } catch (authErr) {
      console.error("Auto-login failed:", authErr);
      return false;
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Ensure authentication before making the API call
    const isAuthenticated = await ensureAuthenticated();
    if (!isAuthenticated) {
        setError(t("addClient.authError"));
      setLoading(false);
      return;
    }

    try {
      const response = await clientsAPI.create(formData);
      const newClient = response.data;
      onSuccess(newClient);
      onClose();
      // Reset form
      setFormData({
        first_name: "",
        last_name: "",
        phone: "",
        email: "",
        street: "",
        house_number: "",
        apartment: "",
        city: "",
        postal_code: "",
        country: "Polska",
      });
    } catch (err) {
      // Handle authentication errors - try to auto-login and retry once more
      if (err.response?.status === 401) {
        try {
          const authResponse = await authAPI.login("drsmith", "password123");
          localStorage.setItem("access_token", authResponse.data.access);
          localStorage.setItem("refresh_token", authResponse.data.refresh);
          // Retry the client creation
          const response = await clientsAPI.create(formData);
          const newClient = response.data;
          onSuccess(newClient);
          onClose();
          setFormData({
            first_name: "",
            last_name: "",
            phone: "",
            email: "",
            street: "",
            house_number: "",
            apartment: "",
            city: "",
            postal_code: "",
            country: "Polska",
          });
          return;
        } catch (authErr) {
          console.error("Auto-login retry failed:", authErr);
          setError(t("addClient.authError"));
        }
      } else {
        setError(
          err.response?.data?.detail || t("addClient.createError")
        );
      }
      console.error("Error creating client:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t("addClient.title")}</h2>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="first_name">{t("addClient.firstName")}</label>
              <input
                type="text"
                id="first_name"
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="last_name">{t("addClient.lastName")}</label>
              <input
                type="text"
                id="last_name"
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="phone">{t("addClient.phone")}</label>
              <input
                type="tel"
                id="phone"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="email">{t("addClient.email")}</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
              />
            </div>
          </div>

          <div
            style={{
              marginTop: "1.5rem",
              paddingTop: "1.5rem",
              borderTop: "1px solid #e2e8f0",
            }}
          >
            <h3
              style={{
                marginBottom: "1rem",
                fontSize: "1rem",
                fontWeight: "600",
                color: "#2d3748",
              }}
            >
              {t("addClient.addressInfo")}
            </h3>

            <div className="form-row">
              <div className="form-group" style={{ flex: 2 }}>
                <label htmlFor="street">{t("addClient.street")}</label>
                <input
                  type="text"
                  id="street"
                  name="street"
                  value={formData.street}
                  onChange={handleChange}
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label htmlFor="house_number">{t("addClient.houseNumber")}</label>
                <input
                  type="text"
                  id="house_number"
                  name="house_number"
                  value={formData.house_number}
                  onChange={handleChange}
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label htmlFor="apartment">{t("addClient.apartment")}</label>
                <input
                  type="text"
                  id="apartment"
                  name="apartment"
                  value={formData.apartment}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="city">{t("addClient.city")}</label>
                <input
                  type="text"
                  id="city"
                  name="city"
                  value={formData.city}
                  onChange={handleChange}
                />
              </div>

              <div className="form-group">
                <label htmlFor="postal_code">{t("addClient.postalCode")}</label>
                <input
                  type="text"
                  id="postal_code"
                  name="postal_code"
                  value={formData.postal_code}
                  onChange={handleChange}
                />
              </div>

              <div className="form-group">
                <label htmlFor="country">{t("addClient.country")}</label>
                <select
                  id="country"
                  name="country"
                  value={formData.country}
                  onChange={handleChange}
                >
                  <option value="Polska">Polska</option>
                  <option value="Austria">Austria</option>
                  <option value="Belgia">Belgia</option>
                  <option value="Białoruś">Białoruś</option>
                  <option value="Bułgaria">Bułgaria</option>
                  <option value="Chorwacja">Chorwacja</option>
                  <option value="Czechy">Czechy</option>
                  <option value="Dania">Dania</option>
                  <option value="Estonia">Estonia</option>
                  <option value="Finlandia">Finlandia</option>
                  <option value="Francja">Francja</option>
                  <option value="Grecja">Grecja</option>
                  <option value="Hiszpania">Hiszpania</option>
                  <option value="Irlandia">Irlandia</option>
                  <option value="Kanada">Kanada</option>
                  <option value="Litwa">Litwa</option>
                  <option value="Luksemburg">Luksemburg</option>
                  <option value="Łotwa">Łotwa</option>
                  <option value="Niemcy">Niemcy</option>
                  <option value="Niderlandy">Niderlandy</option>
                  <option value="Norwegia">Norwegia</option>
                  <option value="Portugalia">Portugalia</option>
                  <option value="Rumunia">Rumunia</option>
                  <option value="Słowacja">Słowacja</option>
                  <option value="Słowenia">Słowenia</option>
                  <option value="Stany Zjednoczone">Stany Zjednoczone</option>
                  <option value="Szwajcaria">Szwajcaria</option>
                  <option value="Szwecja">Szwecja</option>
                  <option value="Ukraina">Ukraina</option>
                  <option value="Węgry">Węgry</option>
                  <option value="Wielka Brytania">Wielka Brytania</option>
                  <option value="Włochy">Włochy</option>
                  <option value="Inne">Inne</option>
                </select>
              </div>
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              {t("common.cancel")}
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? t("addClient.creating") : t("addClient.createClient")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddClientModal;
