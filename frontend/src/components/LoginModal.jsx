import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { authAPI } from '../services/api'
import './modals/Modal.css'

const LoginModal = ({ isOpen, onClose, onSuccess, isRequired = false }) => {
  const { t } = useTranslation()
  const [formData, setFormData] = useState({
    username: '',
    password: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await authAPI.login(formData.username, formData.password)
      localStorage.setItem('access_token', response.data.access)
      localStorage.setItem('refresh_token', response.data.refresh)
      onSuccess(formData.username)
    } catch (err) {
      setError(err.response?.data?.detail || t('login.loginFailed'))
      console.error('Error logging in:', err)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div
      className={`modal-overlay${isRequired ? " modal-overlay--login" : ""}`}
      onClick={isRequired ? undefined : onClose}
    >
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t('login.title')}</h2>
          {!isRequired && (
            <button className="modal-close" onClick={onClose}>×</button>
          )}
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-group">
            <label htmlFor="username">{t('login.username')}</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              autoFocus
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">{t('login.password')}</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
            />
          </div>

          <div className="modal-actions">
            {!isRequired && (
              <button type="button" className="btn-secondary" onClick={onClose}>
                {t('common.cancel')}
              </button>
            )}
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? t('login.loggingIn') : t('login.login')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default LoginModal
