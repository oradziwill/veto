import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { servicesAPI } from '../../services/api'
import './Tabs.css'

const VAT_RATES = ['23', '8', '5', '0', 'zw', 'oo', 'np']

const EMPTY_FORM = { name: '', code: '', price: '', description: '' }

const ServiceCatalogTab = () => {
  const { t } = useTranslation()
  const [services, setServices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState(EMPTY_FORM)
  const [isCreating, setIsCreating] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState(null)
  const [deletingId, setDeletingId] = useState(null)

  const fetchServices = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await servicesAPI.list()
      setServices(res.data.results || res.data)
    } catch {
      setError(t('serviceCatalog.loadError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchServices() }, [])

  const startEdit = (svc) => {
    setEditingId(svc.id)
    setEditForm({ name: svc.name, code: svc.code || '', price: svc.price, description: svc.description || '' })
    setFormError(null)
    setIsCreating(false)
  }

  const cancelEdit = () => { setEditingId(null); setFormError(null) }

  const handleSaveEdit = async () => {
    if (!editForm.name.trim()) { setFormError(t('serviceCatalog.nameRequired')); return }
    setSaving(true)
    setFormError(null)
    try {
      const res = await servicesAPI.update(editingId, {
        name: editForm.name.trim(),
        code: editForm.code.trim(),
        price: editForm.price || '0.00',
        description: editForm.description.trim(),
      })
      setServices(prev => prev.map(s => s.id === editingId ? res.data : s))
      setEditingId(null)
    } catch (err) {
      const data = err.response?.data
      setFormError(data ? Object.values(data).flat().join(' ') : t('serviceCatalog.saveError'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm(t('serviceCatalog.deleteConfirm'))) return
    setDeletingId(id)
    try {
      await servicesAPI.delete(id)
      setServices(prev => prev.filter(s => s.id !== id))
    } catch {
      alert(t('serviceCatalog.deleteError'))
    } finally {
      setDeletingId(null)
    }
  }

  const startCreate = () => {
    setIsCreating(true)
    setCreateForm(EMPTY_FORM)
    setFormError(null)
    setEditingId(null)
  }

  const cancelCreate = () => { setIsCreating(false); setFormError(null) }

  const handleSaveCreate = async () => {
    if (!createForm.name.trim()) { setFormError(t('serviceCatalog.nameRequired')); return }
    setSaving(true)
    setFormError(null)
    try {
      const res = await servicesAPI.create({
        name: createForm.name.trim(),
        code: createForm.code.trim(),
        price: createForm.price || '0.00',
        description: createForm.description.trim(),
      })
      setServices(prev => [...prev, res.data].sort((a, b) => a.name.localeCompare(b.name)))
      setIsCreating(false)
    } catch (err) {
      const data = err.response?.data
      setFormError(data ? Object.values(data).flat().join(' ') : t('serviceCatalog.saveError'))
    } finally {
      setSaving(false)
    }
  }

  const inputStyle = {
    width: '100%', border: '1px solid #cbd5e0', borderRadius: '4px',
    padding: '0.35rem 0.5rem', fontSize: '0.9rem',
  }

  return (
    <div className="tab-container">
      <div className="tab-header">
        {!isCreating && (
          <button className="btn-primary" onClick={startCreate}>
            {t('serviceCatalog.addService')}
          </button>
        )}
      </div>

      <div className="tab-content-wrapper">
        {loading && <div className="loading-message">{t('common.loading')}</div>}
        {error && <div className="error-message">{error}</div>}

        {!loading && !error && (
          <div className="inventory-table">
            <table>
              <thead>
                <tr>
                  <th>{t('serviceCatalog.name')}</th>
                  <th>{t('serviceCatalog.code')}</th>
                  <th style={{ textAlign: 'right' }}>{t('serviceCatalog.price')}</th>
                  <th>{t('serviceCatalog.description')}</th>
                  <th style={{ width: '120px' }}></th>
                </tr>
              </thead>
              <tbody>
                {isCreating && (
                  <tr style={{ background: '#f0fff4' }}>
                    <td style={{ padding: '0.4rem' }}>
                      <input
                        style={inputStyle}
                        value={createForm.name}
                        onChange={e => setCreateForm(p => ({ ...p, name: e.target.value }))}
                        placeholder={t('serviceCatalog.namePlaceholder')}
                        autoFocus
                      />
                    </td>
                    <td style={{ padding: '0.4rem' }}>
                      <input
                        style={inputStyle}
                        value={createForm.code}
                        onChange={e => setCreateForm(p => ({ ...p, code: e.target.value }))}
                        placeholder={t('serviceCatalog.codePlaceholder')}
                      />
                    </td>
                    <td style={{ padding: '0.4rem' }}>
                      <input
                        style={{ ...inputStyle, textAlign: 'right' }}
                        type="number"
                        min="0"
                        step="0.01"
                        value={createForm.price}
                        onChange={e => setCreateForm(p => ({ ...p, price: e.target.value }))}
                        placeholder="0.00"
                      />
                    </td>
                    <td style={{ padding: '0.4rem' }}>
                      <input
                        style={inputStyle}
                        value={createForm.description}
                        onChange={e => setCreateForm(p => ({ ...p, description: e.target.value }))}
                        placeholder={t('serviceCatalog.descriptionPlaceholder')}
                      />
                    </td>
                    <td style={{ padding: '0.4rem', whiteSpace: 'nowrap' }}>
                      {formError && !editingId && (
                        <div style={{ color: '#c53030', fontSize: '0.75rem', marginBottom: '0.3rem' }}>{formError}</div>
                      )}
                      <button className="btn-primary" style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}
                        disabled={saving} onClick={handleSaveCreate}>
                        {saving ? '…' : t('common.save')}
                      </button>
                      {' '}
                      <button className="btn-secondary" style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}
                        onClick={cancelCreate}>
                        {t('common.cancel')}
                      </button>
                    </td>
                  </tr>
                )}

                {services.length === 0 && !isCreating ? (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '2rem', color: '#718096' }}>
                      {t('serviceCatalog.empty')}
                    </td>
                  </tr>
                ) : (
                  services.map(svc => (
                    <tr key={svc.id}>
                      {editingId === svc.id ? (
                        <>
                          <td style={{ padding: '0.4rem' }}>
                            <input
                              style={inputStyle}
                              value={editForm.name}
                              onChange={e => setEditForm(p => ({ ...p, name: e.target.value }))}
                              autoFocus
                            />
                          </td>
                          <td style={{ padding: '0.4rem' }}>
                            <input
                              style={inputStyle}
                              value={editForm.code}
                              onChange={e => setEditForm(p => ({ ...p, code: e.target.value }))}
                            />
                          </td>
                          <td style={{ padding: '0.4rem' }}>
                            <input
                              style={{ ...inputStyle, textAlign: 'right' }}
                              type="number"
                              min="0"
                              step="0.01"
                              value={editForm.price}
                              onChange={e => setEditForm(p => ({ ...p, price: e.target.value }))}
                            />
                          </td>
                          <td style={{ padding: '0.4rem' }}>
                            <input
                              style={inputStyle}
                              value={editForm.description}
                              onChange={e => setEditForm(p => ({ ...p, description: e.target.value }))}
                            />
                          </td>
                          <td style={{ padding: '0.4rem', whiteSpace: 'nowrap' }}>
                            {formError && editingId === svc.id && (
                              <div style={{ color: '#c53030', fontSize: '0.75rem', marginBottom: '0.3rem' }}>{formError}</div>
                            )}
                            <button className="btn-primary" style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}
                              disabled={saving} onClick={handleSaveEdit}>
                              {saving ? '…' : t('common.save')}
                            </button>
                            {' '}
                            <button className="btn-secondary" style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}
                              onClick={cancelEdit}>
                              {t('common.cancel')}
                            </button>
                          </td>
                        </>
                      ) : (
                        <>
                          <td>{svc.name}</td>
                          <td style={{ color: '#718096', fontSize: '0.85rem' }}>{svc.code || '—'}</td>
                          <td style={{ textAlign: 'right', fontWeight: '500' }}>{svc.price} zł</td>
                          <td style={{ color: '#718096', fontSize: '0.85rem' }}>{svc.description || '—'}</td>
                          <td style={{ whiteSpace: 'nowrap' }}>
                            <button className="btn-link" style={{ fontSize: '0.85rem' }}
                              onClick={() => startEdit(svc)}>
                              {t('common.edit')}
                            </button>
                            {' '}
                            <button className="btn-link" style={{ fontSize: '0.85rem', color: '#e53e3e' }}
                              disabled={deletingId === svc.id}
                              onClick={() => handleDelete(svc.id)}>
                              {deletingId === svc.id ? '…' : t('common.delete')}
                            </button>
                          </td>
                        </>
                      )}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default ServiceCatalogTab
