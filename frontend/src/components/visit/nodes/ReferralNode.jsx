import React from 'react'

const URGENCY_STYLES = {
  cito:    { bg: '#fef2f2', border: '#dc2626', color: '#7f1d1d' },
  urgent:  { bg: '#fffbeb', border: '#d97706', color: '#78350f' },
  routine: { bg: '#f0fdf4', border: '#16a34a', color: '#14532d' },
}

export default function ReferralNode({ node, onComplete }) {
  const urgency = URGENCY_STYLES[node.urgency || 'routine']
  return (
    <div className="pw-node pw-node--referral">
      <div
        className="pw-urgency-banner"
        style={{ background: urgency.bg, borderLeft: `4px solid ${urgency.border}`, color: urgency.color }}
      >
        <strong>Skierowanie: {node.specialty}</strong>
      </div>
      <p className="pw-referral-reason">{node.reason}</p>
      {node.notes && <p className="pw-referral-notes">{node.notes}</p>}
      <button type="button" className="pw-btn-primary" onClick={() => onComplete({ node })}>
        Zastosuj i zakończ procedurę
      </button>
    </div>
  )
}
