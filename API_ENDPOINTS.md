# API Endpoints Documentation

## Base URL
`http://localhost:8000/api`

## Authentication
All endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <access_token>
```

## Endpoints

### Authentication
- `POST /api/auth/token/` - Get JWT access and refresh tokens
- `POST /api/auth/token/refresh/` - Refresh access token
- `GET /api/me/` - Get current user information

### Patients
- `GET /api/patients/` - List all patients (supports `?search=term` query param)
- `GET /api/patients/{id}/` - Get patient details
- `POST /api/patients/` - Create new patient
- `PUT /api/patients/{id}/` - Update patient
- `DELETE /api/patients/{id}/` - Delete patient

### Appointments (Visits)
- `GET /api/appointments/` - List appointments (supports `?from=ISO_DATE&to=ISO_DATE` query params)
- `GET /api/appointments/{id}/` - Get appointment details
- `POST /api/appointments/` - Create new appointment
- `PUT /api/appointments/{id}/` - Update appointment
- `DELETE /api/appointments/{id}/` - Delete appointment
- `GET /api/appointments/mine/` - Get current user's appointments

### Inventory
- `GET /api/inventory/` - List inventory items (supports `?search=term&category=category` query params)
- `GET /api/inventory/{id}/` - Get inventory item details
- `POST /api/inventory/` - Create new inventory item
- `PUT /api/inventory/{id}/` - Update inventory item
- `DELETE /api/inventory/{id}/` - Delete inventory item

### Clients
- `GET /api/clients/` - List all clients (supports `?search=term` query param)
- `GET /api/clients/{id}/` - Get client details
- `POST /api/clients/` - Create new client
- `PUT /api/clients/{id}/` - Update client
- `DELETE /api/clients/{id}/` - Delete client

## Frontend Integration

The frontend uses the API service layer located at `frontend/src/services/api.js` which provides:
- `patientsAPI` - All patient-related API calls
- `appointmentsAPI` - All appointment-related API calls
- `inventoryAPI` - All inventory-related API calls
- `clientsAPI` - All client-related API calls
- `authAPI` - Authentication API calls

All API calls automatically include the JWT token from localStorage if available.

