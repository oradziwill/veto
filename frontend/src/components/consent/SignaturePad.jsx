import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from 'react'

/**
 * Canvas signature capture (Wacom pen / mouse / touch via Pointer Events).
 */
const SignaturePad = forwardRef(function SignaturePad(
  { width = 520, height = 220, disabled, onStrokeChange, clearLabel },
  ref
) {
  const canvasRef = useRef(null)
  const drawing = useRef(false)
  const last = useRef(null)

  const clearCanvas = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, width, height)
    ctx.strokeStyle = '#1a202c'
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    onStrokeChange?.(false)
  }, [width, height, onStrokeChange])

  useImperativeHandle(
    ref,
    () => ({
      clear: clearCanvas,
      getCanvas: () => canvasRef.current,
    }),
    [clearCanvas]
  )

  useEffect(() => {
    clearCanvas()
  }, [clearCanvas])

  const getPos = (e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    }
  }

  const onPointerDown = (e) => {
    if (disabled) return
    e.preventDefault()
    try {
      e.target.setPointerCapture(e.pointerId)
    } catch (_) {}
    drawing.current = true
    last.current = getPos(e)
  }

  const onPointerMove = (e) => {
    if (!drawing.current || disabled) return
    e.preventDefault()
    const p = getPos(e)
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    ctx.beginPath()
    ctx.moveTo(last.current.x, last.current.y)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
    last.current = p
    onStrokeChange?.(true)
  }

  const onPointerUp = (e) => {
    if (!drawing.current) return
    drawing.current = false
    last.current = null
    try {
      e.target.releasePointerCapture(e.pointerId)
    } catch (_) {}
  }

  return (
    <div>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        style={{
          width: '100%',
          maxWidth: width,
          height: 'auto',
          touchAction: 'none',
          border: '1px solid #cbd5e0',
          borderRadius: 8,
          cursor: disabled ? 'default' : 'crosshair',
          background: '#fff',
          display: 'block',
        }}
      />
      <button
        type="button"
        onClick={clearCanvas}
        disabled={disabled}
        style={{
          marginTop: 8,
          padding: '0.4rem 0.75rem',
          background: '#edf2f7',
          border: '1px solid #cbd5e0',
          borderRadius: 6,
          cursor: disabled ? 'not-allowed' : 'pointer',
        }}
      >
        {clearLabel}
      </button>
    </div>
  )
})

export default SignaturePad
