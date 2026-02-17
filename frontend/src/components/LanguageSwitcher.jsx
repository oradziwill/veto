import React, { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'

const LANGUAGES = [
  { code: 'pl', label: 'Polski', flag: '🇵🇱' },
  { code: 'en', label: 'English', flag: '🇬🇧' },
]

const LanguageSwitcher = () => {
  const { i18n } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef(null)

  const currentLang = LANGUAGES.find((l) => l.code === (i18n.language?.slice(0, 2) || 'pl')) || LANGUAGES[0]

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  const changeLanguage = (code) => {
    i18n.changeLanguage(code)
    localStorage.setItem('veto-language', code)
    setIsOpen(false)
  }

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          padding: '0.35rem 0.6rem',
          fontSize: '0.95rem',
          background: 'white',
          color: '#2f855a',
          border: '2px solid white',
          borderRadius: '6px',
          cursor: 'pointer',
          boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
        }}
        title={currentLang.label}
      >
        <span style={{ fontSize: '1.1rem' }}>{currentLang.flag}</span>
        <span style={{ fontWeight: 500 }}>{currentLang.code.toUpperCase()}</span>
        <span style={{ fontSize: '0.7rem', marginLeft: '0.15rem' }}>▼</span>
      </button>
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '0.25rem',
            minWidth: '120px',
            backgroundColor: 'white',
            borderRadius: '6px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            border: '1px solid #e2e8f0',
            zIndex: 1000,
            overflow: 'hidden',
          }}
        >
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => changeLanguage(lang.code)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                width: '100%',
                padding: '0.5rem 0.75rem',
                border: 'none',
                background: currentLang.code === lang.code ? '#e6fffa' : 'transparent',
                cursor: 'pointer',
                fontSize: '0.9rem',
                textAlign: 'left',
              }}
            >
              <span style={{ fontSize: '1.1rem' }}>{lang.flag}</span>
              <span>{lang.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default LanguageSwitcher
