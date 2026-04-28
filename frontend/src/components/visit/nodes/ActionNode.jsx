import React, { useState } from 'react'

const URGENCY_STYLES = {
  cito:    { bg: '#fef2f2', border: '#dc2626', color: '#7f1d1d', label: 'CITO' },
  urgent:  { bg: '#fffbeb', border: '#d97706', color: '#78350f', label: 'PILNE' },
  routine: { bg: '#f0fdf4', border: '#16a34a', color: '#14532d', label: 'Rutynowe' },
}

export default function ActionNode({ node, onComplete }) {
  const [checked, setChecked] = useState({})

  const toggle = (id) => setChecked(prev => ({ ...prev, [id]: !prev[id] }))

  const allRequired = (node.checklist || [])
    .filter(c => c.required)
    .every(c => checked[c.id])

  const urgency = URGENCY_STYLES[node.urgency || 'routine']

  return (
    <div className="pw-node pw-node--action">
      <div
        className="pw-urgency-banner"
        style={{ background: urgency.bg, borderLeft: `4px solid ${urgency.border}`, color: urgency.color }}
      >
        <strong>{urgency.label}</strong>
        {node.body && <span> — {node.body}</span>}
      </div>

      {node.checklist && node.checklist.length > 0 && (
        <div className="pw-checklist">
          {node.checklist.map((item) => (
            <label key={item.id} className="pw-check-item">
              <input
                type="checkbox"
                checked={!!checked[item.id]}
                onChange={() => toggle(item.id)}
              />
              <span className={item.required ? 'pw-check-required' : ''}>
                {item.text}
                {item.required && <span className="pw-req-mark"> *</span>}
              </span>
            </label>
          ))}
        </div>
      )}

      {node.labTests && node.labTests.length > 0 && (
        <div className="pw-lab-tests">
          <p className="pw-lab-title">Zalecane badania:</p>
          <ul>
            {node.labTests.map((t, i) => (
              <li key={i}>
                <strong>{t.name}</strong>
                {t.priority === 'first_line' && <span className="pw-lab-badge pw-lab-badge--1">I linia</span>}
                {t.priority === 'second_line' && <span className="pw-lab-badge pw-lab-badge--2">II linia</span>}
                {t.notes && <span className="pw-lab-notes"> — {t.notes}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        className="pw-btn-primary"
        onClick={() => onComplete({ node, checked })}
        disabled={!allRequired}
        title={!allRequired ? 'Zaznacz wszystkie wymagane pozycje (*) aby kontynuować' : ''}
      >
        {allRequired ? 'Zastosuj i zakończ procedurę' : 'Zaznacz wymagane pozycje (*)'}
      </button>
    </div>
  )
}
