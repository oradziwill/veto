import React, { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import PatientsTab from '../components/tabs/PatientsTab'
import VisitsTab from '../components/tabs/VisitsTab'
import CalendarTab from '../components/tabs/CalendarTab'
import InventoryTab from '../components/tabs/InventoryTab'
import AIAssistantTab from '../components/tabs/AIAssistantTab'
import LoginModal from '../components/LoginModal'
import { authAPI } from '../services/api'
import './DoctorsView.css'

const DoctorsView = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') || 'patients'
  const [showLoginModal, setShowLoginModal] = useState(false)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  // Auto-login on mount for development
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token')
      if (token) {
        try {
          await authAPI.me()
          setIsAuthenticated(true)
        } catch (err) {
          // Token invalid, clear it
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          setIsAuthenticated(false)
        }
      } else {
        // Try auto-login with default credentials
        try {
          const response = await authAPI.login('drsmith', 'password123')
          localStorage.setItem('access_token', response.data.access)
          localStorage.setItem('refresh_token', response.data.refresh)
          setIsAuthenticated(true)
        } catch (err) {
          // Auto-login failed, show login modal
          setIsAuthenticated(false)
        }
      }
    }
    checkAuth()
  }, [])

  const handleTabChange = (tabId) => {
    setSearchParams({ tab: tabId })
  }

  const tabs = [
    { id: 'patients', label: 'Patients', icon: '🐾' },
    { id: 'visits', label: 'Visits', icon: '📋' },
    { id: 'calendar', label: 'Calendar', icon: '📅' },
    { id: 'inventory', label: 'Inventory', icon: '📦' },
    { id: 'ai-assistant', label: 'AI Assistant', icon: '🤖' },
  ]

  const renderTabContent = () => {
    switch (activeTab) {
      case 'patients':
        return <PatientsTab />
      case 'visits':
        return <VisitsTab />
      case 'calendar':
        return <CalendarTab />
      case 'inventory':
        return <InventoryTab />
      case 'ai-assistant':
        return <AIAssistantTab />
      default:
        return <PatientsTab />
    }
  }

  return (
    <div className="doctors-view">
      <header className="doctors-header">
        <div className="header-content">
          <h1 className="header-title">
            Veto Clinic Management
          </h1>
          <div className="header-user">
            {isAuthenticated ? (
              <>
                <span className="user-name">Dr. Smith</span>
                <div className="user-avatar">DS</div>
              </>
            ) : (
              <button
                className="btn-secondary"
                onClick={() => setShowLoginModal(true)}
                style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
              >
                Login
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="doctors-content">
        <nav className="doctors-nav">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => handleTabChange(tab.id)}
            >
              <span className="tab-icon">{tab.icon}</span>
              <span className="tab-label">{tab.label}</span>
            </button>
          ))}
        </nav>

        <main className="doctors-main">
          <div className="tab-content">
            {renderTabContent()}
          </div>
        </main>
      </div>

      <LoginModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
        onSuccess={() => {
          setIsAuthenticated(true)
          setShowLoginModal(false)
        }}
      />
    </div>
  )
}

export default DoctorsView
