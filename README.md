# Veto - Veterinary Clinic Management System

A full-stack web application for managing veterinary clinics, built with Django REST Framework (backend) and React (frontend).

## Features

- **Patient Management**: Create and manage patient (animal) records
- **Client Management**: Manage client (pet owner) information
- **Appointment Scheduling**: Track and manage veterinary appointments
- **Inventory Management**: Manage clinic inventory and supplies
- **Multi-clinic Support**: Support for multiple veterinary clinics
- **JWT Authentication**: Secure API authentication

## Tech Stack

### Backend

- **Django 5.2+**: Web framework
- **Django REST Framework**: API framework
- **SQLite**: Database (development)
- **djangorestframework-simplejwt**: JWT authentication
- **django-cors-headers**: CORS support

### Frontend

- **React 18**: UI library
- **Vite**: Build tool and dev server
- **Axios**: HTTP client for API calls
- **React Router**: Client-side routing

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.13+**
- **Node.js 16+** and npm
- **Git**

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd veto
```

### 2. Backend Setup

The backend already includes a virtual environment with dependencies installed. If you need to set it up from scratch:

```bash
cd backend

# Create virtual environment (if not already created)
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
./venv/bin/python manage.py migrate

# (Optional) Create a superuser for admin access
./venv/bin/python manage.py createsuperuser

# (Optional) Seed initial data
./venv/bin/python manage.py seed_data
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

## Running the Application

### Quick Start

You need to run both the backend and frontend servers:

#### Terminal 1 - Backend (Django)

```bash
cd backend
./venv/bin/python manage.py runserver
```

The backend server will start on `http://localhost:8000`

#### Terminal 2 - Frontend (React/Vite)

```bash
cd frontend
npm run dev
```

The frontend server will start on `http://localhost:3000`

### Access the Application

Once both servers are running:

- **Frontend Application**: Open your browser and go to `http://localhost:3000`
- **Backend API**: `http://localhost:8000/api/`
- **Django Admin**: `http://localhost:8000/admin/`

## Running in Background

### Backend

To run the Django server in the background:

```bash
cd backend
./venv/bin/python manage.py runserver > server.log 2>&1 &
```

To stop it:

```bash
lsof -ti:8000 | xargs kill
```

### Frontend

To run the frontend in the background:

```bash
cd frontend
npm run dev > dev.log 2>&1 &
```

## API Documentation

API endpoints are documented in [API_ENDPOINTS.md](./API_ENDPOINTS.md).

### Authentication

All API endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <access_token>
```

To get a token, use the `/api/auth/token/` endpoint with your username and password.

## Project Structure

```
veto/
├── backend/                 # Django backend
│   ├── apps/               # Django applications
│   │   ├── accounts/       # User management
│   │   ├── clients/        # Client (pet owner) management
│   │   ├── patients/       # Patient (animal) management
│   │   ├── scheduling/     # Appointment management
│   │   ├── inventory/      # Inventory management
│   │   ├── medical/        # Medical records
│   │   └── tenancy/        # Multi-clinic support
│   ├── config/             # Django project settings
│   ├── manage.py           # Django management script
│   ├── requirements.txt    # Python dependencies
│   └── venv/               # Virtual environment
│
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── services/       # API service layer
│   │   └── views/          # Page views
│   ├── package.json        # Node.js dependencies
│   └── vite.config.js      # Vite configuration
│
├── API_ENDPOINTS.md        # API documentation
└── README.md              # This file
```

## Troubleshooting

### Port Already in Use

If you get a "port already in use" error:

**Backend (port 8000):**

```bash
lsof -ti:8000 | xargs kill -9
```

**Frontend (port 3000):**

```bash
lsof -ti:3000 | xargs kill -9
```

### Django Import Errors in IDE

If your IDE shows import errors for Django modules:

1. Ensure your IDE is configured to use the virtual environment
2. Check `.vscode/settings.json` is configured correctly:
   ```json
   {
     "python.defaultInterpreterPath": "${workspaceFolder}/backend/venv/bin/python"
   }
   ```
3. Reload your IDE window

### Database Issues

If you need to reset the database:

```bash
cd backend
rm db.sqlite3
./venv/bin/python manage.py migrate
./venv/bin/python manage.py createsuperuser
```

### Frontend Not Connecting to Backend

- Ensure the backend server is running on port 8000
- Check that CORS is properly configured in `backend/config/settings.py`
- Verify the API base URL in `frontend/src/services/api.js`

### Authentication Issues

- Make sure you're logged in through the frontend
- Check browser console for authentication errors
- Verify JWT tokens are being stored in localStorage

## Development

### Running Tests

**Backend:**

```bash
cd backend
./venv/bin/python manage.py test
```

**Frontend:**

```bash
cd frontend
npm test
```

### Code Quality

The project uses:

- **Ruff**: Python linting and formatting
- **Black**: Python code formatting
- **ESLint**: JavaScript linting (if configured)

## Additional Resources

- [Backend Server Guide](./backend/START_SERVER.md)
- [Frontend README](./frontend/README.md)
- [API Endpoints Documentation](./API_ENDPOINTS.md)
- [How to Add Data](./backend/HOW_TO_ADD_DATA.md)

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
