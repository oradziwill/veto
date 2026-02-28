import axios from "axios";

// Use relative URL to go through Vite proxy, or absolute URL if proxy not available
// The vite.config.js proxies /api/* to http://localhost:8000/api/*
const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add token to requests if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Log connection errors for debugging
    if (
      error.code === "ERR_NETWORK" ||
      error.message?.includes("Network Error")
    ) {
      console.error("Network Error - Cannot reach Django server:", {
        url: error.config?.url,
        baseURL: error.config?.baseURL,
        message: error.message,
        code: error.code,
      });
    }

    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      // Notify the app to show login (skip for login requests themselves)
      if (!error.config?.url?.includes("/auth/token/")) {
        window.dispatchEvent(new CustomEvent("auth:logout"));
      }
    }
    return Promise.reject(error);
  }
);

// API endpoints
export const patientsAPI = {
  list: (params) => api.get("/patients/", { params }),
  get: (id) => api.get(`/patients/${id}/`),
  create: (data) => api.post("/patients/", data),
  update: (id, data) => api.put(`/patients/${id}/`, data),
  delete: (id) => api.delete(`/patients/${id}/`),
};

export const appointmentsAPI = {
  list: (params) => api.get("/appointments/", { params }),
  get: (id) => api.get(`/appointments/${id}/`),
  create: (data) => api.post("/appointments/", data),
  update: (id, data) => api.put(`/appointments/${id}/`, data),
  delete: (id) => api.delete(`/appointments/${id}/`),
  mine: () => api.get("/appointments/mine/"),
};

export const inventoryAPI = {
  list: (params) => api.get("/inventory/", { params }),
  get: (id) => api.get(`/inventory/${id}/`),
  create: (data) => api.post("/inventory/", data),
  update: (id, data) => api.put(`/inventory/${id}/`, data),
  delete: (id) => api.delete(`/inventory/${id}/`),
};

export const clientsAPI = {
  list: (params) => {
    // Convert 'search' to 'q' to match API documentation
    if (params?.search) {
      params = { ...params, q: params.search };
      delete params.search;
    }
    return api.get("/clients/", { params });
  },
  get: (id) => api.get(`/clients/${id}/`),
  create: (data) => api.post("/clients/", data),
  update: (id, data) => api.put(`/clients/${id}/`, data),
  delete: (id) => api.delete(`/clients/${id}/`),
  inMyClinic: () => api.get("/clients/", { params: { in_my_clinic: 1 } }),
};

export const authAPI = {
  login: (username, password) =>
    api.post("/auth/token/", { username, password }),
  refresh: (refreshToken) =>
    api.post("/auth/token/refresh/", { refresh: refreshToken }),
  me: () => api.get("/me/"),
};

export const vetsAPI = {
  list: () => api.get("/vets/"),
  get: (id) => api.get(`/vets/${id}/`),
};

export const availabilityAPI = {
  get: (params) => api.get("/availability/", { params }),
  rooms: (params) => api.get("/availability/rooms/", { params }),
};

export const roomsAPI = {
  list: (params) => api.get("/rooms/", { params }),
};

export const patientHistoryAPI = {
  list: (patientId) => api.get(`/patients/${patientId}/history/`),
  create: (patientId, data) =>
    api.post(`/patients/${patientId}/history/`, data),
};

export const patientAISummaryAPI = {
  get: (patientId) => api.get(`/patients/${patientId}/ai-summary/`),
};

export const servicesAPI = {
  list: (params) => api.get("/billing/services/", { params }),
  get: (id) => api.get(`/billing/services/${id}/`),
};

export const invoicesAPI = {
  list: (params) => api.get("/billing/invoices/", { params }),
  get: (id) => api.get(`/billing/invoices/${id}/`),
  create: (data) => api.post("/billing/invoices/", data),
  update: (id, data) => api.put(`/billing/invoices/${id}/`, data),
};

export default api;
