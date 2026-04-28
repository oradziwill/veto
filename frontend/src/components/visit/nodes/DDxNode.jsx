import React from 'react'

const LIKELIHOOD_LABEL = {
  common: 'Częsta',
  uncommon: 'Rzadka',
  rare: 'Bardzo rzadka',
}

const LIKELIHOOD_COLOR = {
  common: '#16a34a',
  uncommon: '#d97706',
  rare: '#9ca3af',
}

export default function DDxNode({ node, onContinue }) {
  return (
    <div className="pw-node pw-node--ddx">
      <p className="pw-ddx-sign">{node.clinicalSign}</p>
      <div className="pw-ddx-list">
        {node.differentials.map((d) => (
          <div key={d.rank} className="pw-ddx-item">
            <div className="pw-ddx-rank">{d.rank}</div>
            <div className="pw-ddx-body">
              <div className="pw-ddx-name">
                {d.name}
                <span
                  className="pw-ddx-likelihood"
                  style={{ color: LIKELIHOOD_COLOR[d.likelihood] }}
                >
                  {LIKELIHOOD_LABEL[d.likelihood]}
                </span>
              </div>
              <ul className="pw-ddx-features">
                {d.keyFeatures.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </div>
          </div>
        ))}
      </div>
      {node.source && (
        <p className="pw-source">Źródło: {node.source}</p>
      )}
      <div className="pw-ddx-actions">
        <button type="button" className="pw-btn-primary" onClick={onContinue}>
          Zastosuj sugestie do formularza
        </button>
      </div>
    </div>
  )
}
