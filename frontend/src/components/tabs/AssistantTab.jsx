import { useState, useEffect, useRef } from "react";
import { ChevronRight, RotateCcw, CheckSquare, Square, AlertTriangle, Zap } from "lucide-react";
import { ASSISTANT_TREE, TRIAGE_MATRIX, TRIAGE_CONFIG } from "../../data/assistantTree";
import "./AssistantTab.css";

// ── Option button ──────────────────────────────────────────────────────────
const OptionBtn = ({ option, onClick }) => {
  const variant = option.variant || "default";
  return (
    <button
      className={`asst-option asst-option--${variant}`}
      onClick={onClick}
    >
      {variant === "cito" && <Zap size={14} className="asst-option-icon" />}
      {variant === "urgent" && <AlertTriangle size={14} className="asst-option-icon" />}
      {option.label}
    </button>
  );
};

// ── Question step ──────────────────────────────────────────────────────────
const QuestionStep = ({ node, onSelect }) => (
  <div className="asst-step">
    <p className="asst-question">{node.question}</p>
    <div className="asst-options">
      {node.options.map((opt) => (
        <OptionBtn key={opt.label} option={opt} onClick={() => onSelect(opt)} />
      ))}
    </div>
  </div>
);

// ── Checklist item ─────────────────────────────────────────────────────────
const CheckItem = ({ text, checked, onToggle }) => (
  <button className={`asst-check-item${checked ? " checked" : ""}`} onClick={onToggle}>
    {checked ? (
      <CheckSquare size={16} className="asst-check-icon checked" />
    ) : (
      <Square size={16} className="asst-check-icon" />
    )}
    <span>{text}</span>
  </button>
);

// ── Action step ────────────────────────────────────────────────────────────
const ActionStep = ({ node, checkedItems, onToggle, onClose }) => (
  <div className="asst-step">
    {node.body && <p className="asst-body">{node.body}</p>}
    {node.checklist && (
      <div className="asst-checklist">
        {node.checklist.map((item, i) => (
          <CheckItem
            key={i}
            text={item}
            checked={!!checkedItems[`${node.id}::${i}`]}
            onToggle={() => onToggle(`${node.id}::${i}`)}
          />
        ))}
      </div>
    )}
    <button className="asst-close-btn" onClick={onClose}>
      Zakończ zadanie
    </button>
  </div>
);

// ── Triage result ──────────────────────────────────────────────────────────
const TriageResult = ({ collectedData, checkedItems, onToggle, onClose }) => {
  const sym = collectedData.sym;
  const timeIdx = parseInt(collectedData.time ?? "4", 10);
  const level = TRIAGE_MATRIX[sym]?.[timeIdx] ?? "Normalny";
  const cfg = TRIAGE_CONFIG[level] ?? TRIAGE_CONFIG["Normalny"];

  return (
    <div className={`asst-step asst-triage asst-triage--${cfg.variant}`}>
      <div className="asst-triage-badge">{level}</div>
      <p className="asst-body">{cfg.body}</p>
      <div className="asst-checklist">
        {cfg.checklist.map((item, i) => (
          <CheckItem
            key={i}
            text={item}
            checked={!!checkedItems[`triage_result::${i}`]}
            onToggle={() => onToggle(`triage_result::${i}`)}
          />
        ))}
      </div>
      <button className="asst-close-btn" onClick={onClose}>
        Zakończ zadanie
      </button>
    </div>
  );
};

// ── Breadcrumb ─────────────────────────────────────────────────────────────
const Breadcrumb = ({ history, onNavigate }) => {
  if (history.length <= 1) return null;
  return (
    <nav className="asst-breadcrumb">
      {history.map((nodeId, idx) => {
        const node = ASSISTANT_TREE[nodeId];
        const isLast = idx === history.length - 1;
        return (
          <span key={nodeId} className="asst-breadcrumb-item">
            {idx > 0 && <ChevronRight size={12} className="asst-breadcrumb-sep" />}
            <button
              className={`asst-breadcrumb-btn${isLast ? " active" : ""}`}
              onClick={() => !isLast && onNavigate(idx)}
              disabled={isLast}
            >
              {node?.label ?? nodeId}
            </button>
          </span>
        );
      })}
    </nav>
  );
};

// ── Main wizard ────────────────────────────────────────────────────────────
const AssistantTab = () => {
  const [history, setHistory] = useState(["start"]);
  const [collectedData, setCollectedData] = useState({});
  const [checkedItems, setCheckedItems] = useState({});
  const [animKey, setAnimKey] = useState(0);
  const contentRef = useRef(null);

  const currentNodeId = history[history.length - 1];
  const currentNode = ASSISTANT_TREE[currentNodeId];

  const advance = (nodeId, data = {}) => {
    setCollectedData((prev) => ({ ...prev, ...data }));
    setHistory((prev) => [...prev, nodeId]);
    setAnimKey((k) => k + 1);
  };

  const navigateTo = (idx) => {
    setHistory((prev) => prev.slice(0, idx + 1));
    setAnimKey((k) => k + 1);
  };

  const reset = () => {
    setHistory(["start"]);
    setCollectedData({});
    setCheckedItems({});
    setAnimKey((k) => k + 1);
  };

  const toggleCheck = (key) => {
    setCheckedItems((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleOptionSelect = (option) => {
    advance(option.nextId, option.data ?? {});
  };

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [animKey]);

  const renderStep = () => {
    if (!currentNode) return <p className="asst-error">Nieznany węzeł: {currentNodeId}</p>;

    if (currentNode.dynamic && currentNodeId === "triage_result") {
      return (
        <TriageResult
          collectedData={collectedData}
          checkedItems={checkedItems}
          onToggle={toggleCheck}
          onClose={reset}
        />
      );
    }

    if (currentNode.type === "question") {
      return <QuestionStep node={currentNode} onSelect={handleOptionSelect} />;
    }

    if (currentNode.type === "action") {
      return (
        <ActionStep node={currentNode} checkedItems={checkedItems} onToggle={toggleCheck} onClose={reset} />
      );
    }

    return null;
  };

  return (
    <div className="asst-root">
      <div className="asst-header">
        <div className="asst-header-left">
          <h2 className="asst-title">Asystent recepcji</h2>
          <Breadcrumb history={history} onNavigate={navigateTo} />
        </div>
        {history.length > 1 && (
          <button className="asst-reset-btn" onClick={reset}>
            <RotateCcw size={14} />
            Od początku
          </button>
        )}
      </div>

      <div className="asst-content" ref={contentRef}>
        {currentNode && (
          <div className="asst-node-title">
            {currentNode.title || currentNode.question
              ? currentNode.title
              : null}
          </div>
        )}
        <div key={animKey} className="asst-step-wrapper asst-fade-in">
          {renderStep()}
        </div>
      </div>
    </div>
  );
};

export default AssistantTab;
