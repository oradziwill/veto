import React, { useReducer, useEffect, useState } from 'react'
import QuestionNode from './nodes/QuestionNode'
import DDxNode from './nodes/DDxNode'
import ActionNode from './nodes/ActionNode'
import ReferralNode from './nodes/ReferralNode'
import './ProcedureWizard.css'

const initialState = {
  phase: 'select',       // 'select' | 'walking' | 'done'
  selectedProcedure: null,
  stack: [],             // nodeId history for back navigation
  collectedData: {},
  currentNodeId: null,
}

function reducer(state, action) {
  switch (action.type) {
    case 'SELECT_PROCEDURE':
      return {
        ...state,
        phase: 'walking',
        selectedProcedure: action.procedure,
        stack: [action.procedure.entry_node_id],
        collectedData: {},
        currentNodeId: action.procedure.entry_node_id,
      }
    case 'GO_TO_NODE':
      return {
        ...state,
        currentNodeId: action.nodeId,
        stack: [...state.stack, action.nodeId],
        collectedData: { ...state.collectedData, ...action.data },
      }
    case 'BACK': {
      if (state.stack.length <= 1) return { ...initialState }
      const newStack = state.stack.slice(0, -1)
      return {
        ...state,
        stack: newStack,
        currentNodeId: newStack[newStack.length - 1],
      }
    }
    case 'FINISH':
      return { ...state, phase: 'done' }
    case 'RESET':
      return { ...initialState }
    default:
      return state
  }
}

function buildResult(state, terminalNode) {
  const { selectedProcedure, collectedData } = state
  const result = {
    procedureName: selectedProcedure?.name || '',
    source: selectedProcedure?.source || '',
    collectedData,
    urgency: null,
    ddxSuggestions: [],
    labTestsSuggested: [],
    notes: '',
  }

  if (!terminalNode) return result

  if (terminalNode.type === 'ddx') {
    result.ddxSuggestions = terminalNode.differentials.map(d => d.name)
    result.urgency = 'routine'
  }
  if (terminalNode.type === 'action') {
    result.urgency = terminalNode.urgency || 'routine'
    result.labTestsSuggested = (terminalNode.labTests || []).map(t => t.name)
    result.notes = terminalNode.body || ''
  }
  if (terminalNode.type === 'referral') {
    result.urgency = terminalNode.urgency || 'routine'
    result.notes = `Skierowanie do: ${terminalNode.specialty}. ${terminalNode.reason}`
  }
  return result
}

export default function ProcedureWizard({ species, onComplete, onClose }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [procedures, setProcedures] = useState([])
  const [loading, setLoading] = useState(false)
  const [terminalNode, setTerminalNode] = useState(null)

  const speciesKey = species?.toLowerCase() === 'cat' ? 'cat' : 'dog'

  useEffect(() => {
    setLoading(true)
    const token = localStorage.getItem('access_token')
    fetch(`/api/procedures/?species=${speciesKey}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(data => setProcedures(Array.isArray(data) ? data : (data.results || [])))
      .catch(() => setProcedures([]))
      .finally(() => setLoading(false))
  }, [speciesKey])

  const fetchProcedureDetail = async (slug) => {
    const token = localStorage.getItem('access_token')
    const r = await fetch(`/api/procedures/${slug}/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return r.json()
  }

  const handleSelectProcedure = async (proc) => {
    const detail = await fetchProcedureDetail(proc.slug)
    dispatch({ type: 'SELECT_PROCEDURE', procedure: detail })
  }

  const handleOption = (opt) => {
    dispatch({ type: 'GO_TO_NODE', nodeId: opt.nextId, data: opt.data || {} })
  }

  const handleActionComplete = ({ node }) => {
    setTerminalNode(node)
    dispatch({ type: 'FINISH' })
  }

  const handleDdxContinue = () => {
    const node = state.selectedProcedure?.nodes?.[state.currentNodeId]
    setTerminalNode(node)
    dispatch({ type: 'FINISH' })
  }

  const handleReferralComplete = ({ node }) => {
    setTerminalNode(node)
    dispatch({ type: 'FINISH' })
  }

  const handleApply = () => {
    const result = buildResult(state, terminalNode)
    onComplete(result)
  }

  const currentNode = state.selectedProcedure?.nodes?.[state.currentNodeId]

  const renderBreadcrumb = () => {
    if (!state.selectedProcedure || state.stack.length <= 1) return null
    const labels = state.stack
      .map(id => state.selectedProcedure.nodes?.[id]?.label || id)
    return (
      <div className="pw-breadcrumb">
        {labels.map((label, i) => (
          <span key={i}>
            {i > 0 && <span className="pw-breadcrumb-sep">›</span>}
            <span className={i === labels.length - 1 ? 'pw-breadcrumb-active' : ''}>{label}</span>
          </span>
        ))}
      </div>
    )
  }

  return (
    <div className="pw-overlay" onClick={onClose}>
      <div className="pw-drawer" onClick={e => e.stopPropagation()}>
        <div className="pw-header">
          <div className="pw-header-left">
            {state.phase !== 'select' && (
              <button type="button" className="pw-back-btn" onClick={() => dispatch({ type: 'BACK' })}>
                ← Wróć
              </button>
            )}
            <span className="pw-title">
              {state.phase === 'select' ? 'Wybierz procedurę' : state.selectedProcedure?.name}
            </span>
          </div>
          <button type="button" className="pw-close-btn" onClick={onClose}>×</button>
        </div>

        <div className="pw-body">
          {/* PHASE: select */}
          {state.phase === 'select' && (
            <div className="pw-select-list">
              {loading && <p className="pw-loading">Ładowanie procedur...</p>}
              {!loading && procedures.length === 0 && (
                <p className="pw-empty">Brak dostępnych procedur dla tego gatunku.</p>
              )}
              {procedures.map(proc => (
                <button
                  key={proc.id}
                  type="button"
                  className="pw-proc-item"
                  onClick={() => handleSelectProcedure(proc)}
                >
                  <span className="pw-proc-name">{proc.name}</span>
                  <div className="pw-proc-tags">
                    {(proc.tags || []).slice(0, 3).map(tag => (
                      <span key={tag} className="pw-tag">{tag}</span>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* PHASE: walking */}
          {state.phase === 'walking' && currentNode && (
            <>
              {renderBreadcrumb()}
              <h3 className="pw-node-title">{currentNode.text || currentNode.title}</h3>
              {currentNode.type === 'question' && (
                <QuestionNode node={currentNode} onSelect={handleOption} />
              )}
              {currentNode.type === 'ddx' && (
                <DDxNode node={currentNode} onContinue={handleDdxContinue} />
              )}
              {currentNode.type === 'action' && (
                <ActionNode node={currentNode} onComplete={handleActionComplete} />
              )}
              {currentNode.type === 'referral' && (
                <ReferralNode node={currentNode} onComplete={handleReferralComplete} />
              )}
            </>
          )}

          {/* PHASE: done */}
          {state.phase === 'done' && (
            <div className="pw-result">
              <div className="pw-result-header">
                <span className="pw-result-icon">✓</span>
                <h3>Procedura zakończona</h3>
              </div>
              <p className="pw-result-proc">{state.selectedProcedure?.name}</p>
              {terminalNode?.type === 'ddx' && (
                <div className="pw-result-section">
                  <strong>Diagnozy różnicowe (DDx):</strong>
                  <ul>
                    {terminalNode.differentials.map((d, i) => (
                      <li key={i}>{d.rank}. {d.name}</li>
                    ))}
                  </ul>
                </div>
              )}
              {terminalNode?.labTests && terminalNode.labTests.length > 0 && (
                <div className="pw-result-section">
                  <strong>Zalecane badania:</strong>
                  <ul>
                    {terminalNode.labTests.map((t, i) => <li key={i}>{t.name}</li>)}
                  </ul>
                </div>
              )}
              {terminalNode?.type === 'referral' && (
                <div className="pw-result-section">
                  <strong>Skierowanie:</strong> {terminalNode.specialty}
                  <p>{terminalNode.reason}</p>
                </div>
              )}
              <button type="button" className="pw-btn-apply" onClick={handleApply}>
                Zastosuj sugestie do formularza wizyty
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
