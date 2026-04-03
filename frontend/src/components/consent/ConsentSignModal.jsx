import React, { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { consentDocumentsAPI } from '../../services/api'
import SignaturePad from './SignaturePad'
import '../modals/Modal.css'

const STEPS = { PREVIEW: 'preview', SIGN: 'sign', DONE: 'done' }

export default function ConsentSignModal({ isOpen, onClose, appointmentId, onCompleted }) {
  const { t } = useTranslation()
  const [step, setStep] = useState(STEPS.PREVIEW)
  const [docId, setDocId] = useState(null)
  const [contentHash, setContentHash] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [signing, setSigning] = useState(false)
  const [hasInk, setHasInk] = useState(false)
  const [done, setDone] = useState(false)
  const sigRef = useRef(null)

  useEffect(() => {
    if (!isOpen || !appointmentId) return

    let cancelled = false
    let objectUrl = null

    const run = async () => {
      setStep(STEPS.PREVIEW)
      setDocId(null)
      setContentHash(null)
      setError(null)
      setHasInk(false)
      setDone(false)
      setLoading(true)
      try {
        const { data } = await consentDocumentsAPI.create({
          appointment: appointmentId,
          location_label: '',
        })
        if (cancelled) return
        setDocId(data.id)
        setContentHash(data.content_hash)
        const blobRes = await consentDocumentsAPI.previewBlob(data.id)
        objectUrl = URL.createObjectURL(blobRes.data)
        if (cancelled) {
          URL.revokeObjectURL(objectUrl)
          return
        }
        setPreviewUrl(objectUrl)
      } catch (e) {
        console.error(e)
        if (!cancelled) setError(t('consent.error'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    run()

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [isOpen, appointmentId])

  const handleClose = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null)
    onClose()
  }

  const submitSign = async () => {
    if (!docId || !contentHash || !sigRef.current?.getCanvas()) return
    const canvas = sigRef.current.getCanvas()
    const blob = await new Promise((resolve) => {
      canvas.toBlob((b) => resolve(b), 'image/png')
    })
    if (!blob || blob.size < 100) {
      setError(t('consent.emptyStroke'))
      return
    }
    setSigning(true)
    setError(null)
    const fd = new FormData()
    fd.append('content_hash', contentHash)
    fd.append('signature', blob, 'signature.png')
    try {
      await consentDocumentsAPI.sign(docId, fd)
      setDone(true)
      setStep(STEPS.DONE)
      onCompleted?.()
    } catch (e) {
      console.error(e)
      setError(t('consent.error'))
    } finally {
      setSigning(false)
    }
  }

  const downloadPdf = async () => {
    if (!docId) return
    try {
      const { data } = await consentDocumentsAPI.downloadUrl(docId)
      if (data.url) window.open(data.url, '_blank', 'noopener,noreferrer')
    } catch (e) {
      console.error(e)
      setError(t('consent.error'))
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: step === STEPS.SIGN ? '640px' : '720px', width: '95%' }}
      >
        <div className="modal-header">
          <h2>{t('consent.modalTitle')}</h2>
          <button type="button" className="modal-close" onClick={handleClose}>
            ×
          </button>
        </div>

        <div style={{ padding: '1rem 1.5rem 1.5rem' }}>
          {loading && <p>{t('common.loading', { defaultValue: 'Loading…' })}</p>}
          {error && (
            <p style={{ color: '#c53030', marginBottom: '0.75rem' }}>{error}</p>
          )}

          {!loading && step === STEPS.PREVIEW && previewUrl && (
            <>
              <p style={{ marginBottom: '0.5rem', color: '#4a5568' }}>{t('consent.preview')}</p>
              <iframe
                title={t('consent.preview')}
                src={previewUrl}
                style={{ width: '100%', height: '420px', border: '1px solid #e2e8f0', borderRadius: 8 }}
              />
              <div style={{ marginTop: '1rem', display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={handleClose}
                  style={{ padding: '0.5rem 1rem', background: 'transparent', border: '1px solid #cbd5e0', borderRadius: 8 }}
                >
                  {t('consent.cancel')}
                </button>
                <button
                  type="button"
                  onClick={() => setStep(STEPS.SIGN)}
                  style={{
                    padding: '0.5rem 1rem',
                    background: '#2b6cb0',
                    color: 'white',
                    border: 'none',
                    borderRadius: 8,
                    fontWeight: 600,
                  }}
                >
                  {t('consent.proceedToSign')}
                </button>
              </div>
            </>
          )}

          {step === STEPS.SIGN && (
            <>
              <p style={{ marginBottom: '0.5rem', color: '#4a5568' }}>{t('consent.signHint')}</p>
              <SignaturePad
                ref={sigRef}
                height={280}
                clearLabel={t('consent.clear')}
                onStrokeChange={setHasInk}
                disabled={signing}
              />
              <div style={{ marginTop: '1rem', display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => setStep(STEPS.PREVIEW)}
                  disabled={signing}
                  style={{ padding: '0.5rem 1rem', background: 'transparent', border: '1px solid #cbd5e0', borderRadius: 8 }}
                >
                  {t('consent.cancel')}
                </button>
                <button
                  type="button"
                  onClick={submitSign}
                  disabled={signing || !hasInk}
                  style={{
                    padding: '0.5rem 1rem',
                    background: !hasInk ? '#a0aec0' : '#2f855a',
                    color: 'white',
                    border: 'none',
                    borderRadius: 8,
                    fontWeight: 600,
                  }}
                >
                  {t('consent.confirmSign')}
                </button>
              </div>
            </>
          )}

          {step === STEPS.DONE && done && (
            <div style={{ textAlign: 'center', padding: '1rem 0' }}>
              <p style={{ fontWeight: 600, color: '#276749', marginBottom: '1rem' }}>{t('consent.success')}</p>
              <button
                type="button"
                onClick={downloadPdf}
                style={{
                  padding: '0.5rem 1rem',
                  background: '#2b6cb0',
                  color: 'white',
                  border: 'none',
                  borderRadius: 8,
                  marginRight: 8,
                }}
              >
                {t('consent.downloadPdf')}
              </button>
              <button
                type="button"
                onClick={handleClose}
                style={{ padding: '0.5rem 1rem', background: '#edf2f7', border: '1px solid #cbd5e0', borderRadius: 8 }}
              >
                {t('consent.close')}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
