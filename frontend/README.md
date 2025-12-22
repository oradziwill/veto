# Veto Frontend

React frontend application for the Veto veterinary clinic management system.

## Features

- **Doctors View** with tabbed interface:
  - **Patients Tab**: View and manage patient records
  - **Visits Tab**: Track and manage veterinary visits
  - **Calendar Tab**: Visual calendar view of appointments
  - **Inventory Tab**: Manage clinic inventory and supplies
  - **AI Assistant Tab**: Interactive AI assistant for veterinary support

## Getting Started

### Prerequisites

- Node.js (v16 or higher)
- npm or yarn

### Installation

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

### Development

Start the development server:
```bash
npm run dev
```

The application will be available at `http://localhost:3000`

### Build

Create a production build:
```bash
npm run build
```

### Preview Production Build

Preview the production build:
```bash
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── tabs/
│   │       ├── PatientsTab.jsx
│   │       ├── VisitsTab.jsx
│   │       ├── CalendarTab.jsx
│   │       ├── InventoryTab.jsx
│   │       ├── AIAssistantTab.jsx
│   │       └── Tabs.css
│   ├── views/
│   │   ├── DoctorsView.jsx
│   │   └── DoctorsView.css
│   ├── App.jsx
│   ├── App.css
│   ├── main.jsx
│   └── index.css
├── index.html
├── package.json
├── vite.config.js
└── README.md
```

## Technology Stack

- **React 18**: UI library
- **React Router**: Client-side routing
- **Vite**: Build tool and dev server
- **Axios**: HTTP client for API calls

## API Integration

The frontend is configured to proxy API requests to the Django backend running on `http://localhost:8000`. The proxy is configured in `vite.config.js`.

## Notes

- The application uses a modern, responsive design with a gradient color scheme
- All components are functional React components using hooks
- The UI is designed to be intuitive and user-friendly for veterinary professionals

