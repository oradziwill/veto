import React from 'react'

const VARIANT_STYLES = {
  cito:   { borderColor: '#dc2626', background: '#fef2f2', color: '#7f1d1d' },
  urgent: { borderColor: '#d97706', background: '#fffbeb', color: '#78350f' },
  normal: { borderColor: '#e2e8f0', background: '#fff',    color: '#1a202c' },
}

export default function QuestionNode({ node, onSelect }) {
  return (
    <div className="pw-node pw-node--question">
      {node.hint && (
        <p className="pw-hint">{node.hint}</p>
      )}
      <div className="pw-options">
        {node.options.map((opt) => {
          const style = VARIANT_STYLES[opt.variant || 'normal']
          return (
            <button
              key={opt.label}
              type="button"
              className={`pw-option pw-option--${opt.variant || 'normal'}`}
              style={style}
              onClick={() => onSelect(opt)}
            >
              {opt.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
