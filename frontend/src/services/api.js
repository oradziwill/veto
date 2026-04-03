import axios from "axios";

// Use relative URL to go through Vite proxy, or absolute URL if proxy not available
// The vite.config.js proxies /api/* to http://localhost:8000/api/*
const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds — prevents infinite loading if backend is unresponsive
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
  list: (params, options = {}) => api.get("/patients/", { params, ...options }),
  get: (id) => api.get(`/patients/${id}/`),
  create: (data) => api.post("/patients/", data),
  update: (id, data) => api.put(`/patients/${id}/`, data),
  delete: (id) => api.delete(`/patients/${id}/`),
  lastVitals: (id) => api.get(`/patients/${id}/last-vitals/`),
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
  list: (params) => api.get("/inventory/items/", { params }),
  get: (id) => api.get(`/inventory/items/${id}/`),
  create: (data) => api.post("/inventory/items/", data),
  update: (id, data) => api.put(`/inventory/items/${id}/`, data),
  delete: (id) => api.delete(`/inventory/items/${id}/`),
  movements: (params) => api.get("/inventory/movements/", { params }),
  recordMovement: (data) => api.post("/inventory/movements/", data),
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

export const queueAPI = {
  list: (params) => api.get("/queue/", { params }),
  add: (data) => api.post("/queue/", data),
  update: (id, data) => api.patch(`/queue/${id}/`, data),
  remove: (id) => api.delete(`/queue/${id}/`),
  moveUp: (id) => api.post(`/queue/${id}/move-up/`),
  moveDown: (id) => api.post(`/queue/${id}/move-down/`),
  call: (id) => api.post(`/queue/${id}/call/`),
  requeue: (id) => api.post(`/queue/${id}/requeue/`),
  done: (id) => api.post(`/queue/${id}/done/`),
};

export const remindersAPI = {
  metrics: () => api.get("/reminders/metrics/"),
  analytics: (params) => api.get("/reminders/analytics/", { params }),
  experimentAttribution: (params) => api.get("/reminders/experiment-attribution/", { params }),
};

export const patientHistoryAPI = {
  list: (patientId) => api.get(`/patients/${patientId}/history/`),
  create: (patientId, data) =>
    api.post(`/patients/${patientId}/history/`, data),
};

export const patientAISummaryAPI = {
  get: (patientId) => api.get(`/patients/${patientId}/ai-summary/`),
};

export const prescriptionsAPI = {
  list: (patientId) => api.get(`/patients/${patientId}/prescriptions/`),
  create: (patientId, data) => api.post(`/patients/${patientId}/prescriptions/`, data),
  get: (id) => api.get(`/prescriptions/${id}/`),
};

export const servicesAPI = {
  list: (params, options = {}) => api.get("/billing/services/", { params, ...options }),
  get: (id) => api.get(`/billing/services/${id}/`),
  create: (data) => api.post("/billing/services/", data),
  update: (id, data) => api.put(`/billing/services/${id}/`, data),
  delete: (id) => api.delete(`/billing/services/${id}/`),
};

export const invoicesAPI = {
  list: (params) => api.get("/billing/invoices/", { params }),
  get: (id) => api.get(`/billing/invoices/${id}/`),
  create: (data) => api.post("/billing/invoices/", data),
  update: (id, data) => api.put(`/billing/invoices/${id}/`, data),
  submitKsef: (id) => api.post(`/billing/invoices/${id}/submit-ksef/`),
};

export const schedulerAPI = {
  // Working hours (regular weekly schedule per vet)
  listWorkingHours: (params) => api.get("/schedule/working-hours/", { params }),
  createWorkingHours: (data) => api.post("/schedule/working-hours/", data),
  updateWorkingHours: (id, data) => api.put(`/schedule/working-hours/${id}/`, data),
  deleteWorkingHours: (id) => api.delete(`/schedule/working-hours/${id}/`),

  // Exceptions (day-offs, custom hours for a specific date)
  listExceptions: (params) => api.get("/schedule/exceptions/", { params }),
  createException: (data) => api.post("/schedule/exceptions/", data),
  updateException: (id, data) => api.patch(`/schedule/exceptions/${id}/`, data),
  deleteException: (id) => api.delete(`/schedule/exceptions/${id}/`),

  // Clinic holidays (full-day clinic closures)
  listHolidays: (params) => api.get("/schedule/holidays/", { params }),
  createHoliday: (data) => api.post("/schedule/holidays/", data),
  updateHoliday: (id, data) => api.patch(`/schedule/holidays/${id}/`, data),
  deleteHoliday: (id) => api.delete(`/schedule/holidays/${id}/`),

  // Clinic working hours (when is the clinic open per weekday)
  listClinicHours: () => api.get("/schedule/clinic-hours/"),
  createClinicHours: (data) => api.post("/schedule/clinic-hours/", data),
  updateClinicHours: (id, data) => api.put(`/schedule/clinic-hours/${id}/`, data),
  deleteClinicHours: (id) => api.delete(`/schedule/clinic-hours/${id}/`),

  // Duty assignments (generated schedule)
  listAssignments: (params) => api.get("/schedule/assignments/", { params }),
  createAssignment: (data) => api.post("/schedule/assignments/", data),
  updateAssignment: (id, data) => api.patch(`/schedule/assignments/${id}/`, data),
  deleteAssignment: (id) => api.delete(`/schedule/assignments/${id}/`),

  // Schedule generation
  generate: (data) => api.post("/schedule/generate/", data),
};

export default api;
