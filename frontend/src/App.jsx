import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import DoctorsView from './views/DoctorsView'
import ReceptionistView from './views/ReceptionistView'
import './App.css'

function App() {
  return (
    <Router>
      <div className="app">
        <Routes>
          <Route path="/" element={<Navigate to="/doctors" replace />} />
          <Route path="/doctors" element={<DoctorsView />} />
          <Route path="/receptionist" element={<ReceptionistView />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
