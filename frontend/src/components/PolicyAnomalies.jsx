import { useState } from 'react'
import { getAnomalies } from '../services/api.js'
import './PolicyAnomalies.css'

// ── Constants ────────────────────────────────────────────────────────────────

const SEVERITY_META = {
  critical: { label: 'Critical', cls: 'anm-sev-critical', icon: '🚨' },
  warning:  { label: 'Warning',  cls: 'anm-sev-warning',  icon: '⚠️' },
  info:     { label: 'Info',     cls: 'anm-sev-info',      icon: 'ℹ️' },
}

const POLICY_META = {
  policy1:  { cls: 'anm-pol-p1',      label: 'Policy 1' },
  policy2:  { cls: 'anm-pol-p2',      label: 'Policy 2' },
  both:     { cls: 'anm-pol-both',    label: 'Both' },
  general:  { cls: 'anm-pol-general', label: 'General' },
}

const DETECTED_BY_META = {
  rule: { label: 'Rule',    cls: 'anm-by-rule' },
  llm:  { label: 'AI',      cls: 'anm-by-llm'  },
}

const CATEGORY_ICONS = {
  premium:   '💰',
  coverage:  '🛡️',
  exclusion: '🚫',
  structure: '📋',
  balance:   '⚖️',
}

// ── Main component ───────────────────────────────────────────────────────────

export default function PolicyAnomalies({ comparisonId }) {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)
  const [data,    setData]    = useState(null)
  const [filter,  setFilter]  = useState('all')   // 'all' | severity value
  const [expanded, setExpanded] = useState(new Set())

  async function handleRun() {
    setError(null)
    setData(null)
    setLoading(true)
    try {
      const result = await getAnomalies(comparisonId)
      setData(result)
      setFilter('all')
      setExpanded(new Set())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function toggleExpand(id) {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const filtered = data
    ? (filter === 'all' ? data.anomalies : data.anomalies.filter((a) => a.severity === filter))
    : []

  return (
    <div className="anm-card card">
      {/* ── Header ────────────────────────────────────────────────── */}
      <div className="anm-header">
        <span className="anm-header-icon">🔍</span>
        <div>
          <h3 className="anm-title">Anomaly Detection</h3>
          <p className="anm-subtitle">
            Scan both policies against industry benchmarks to surface unusual,
            missing, or risky characteristics
          </p>
        </div>
        <button
          className="btn btn-primary anm-run-btn"
          onClick={handleRun}
          disabled={loading}
        >
          {loading
            ? <><span className="btn-spinner" /> Scanning…</>
            : data ? '🔄 Re-scan' : '🔍 Run Scan'}
        </button>
      </div>

      {/* ── Error ─────────────────────────────────────────────────── */}
      {error && (
        <div className="alert alert-error" role="alert">
          <strong>Scan failed:</strong> {error}
        </div>
      )}

      {/* ── Summary bar ───────────────────────────────────────────── */}
      {data && (
        <>
          <SummaryBar
            summary={data.summary}
            policy1Name={data.policy1_name}
            policy2Name={data.policy2_name}
            filter={filter}
            onFilter={setFilter}
          />

          {/* ── LLM insights ──────────────────────────────────────── */}
          {data.llm_insights?.length > 0 && (
            <div className="anm-insights">
              <span className="anm-insights-label">💡 AI Insights</span>
              <ul className="anm-insights-list">
                {data.llm_insights.map((ins, i) => (
                  <li key={i} className="anm-insight-item">{ins}</li>
                ))}
              </ul>
            </div>
          )}

          {/* ── Anomaly list ──────────────────────────────────────── */}
          {filtered.length === 0 ? (
            <div className="anm-empty">
              <span className="anm-empty-icon">✅</span>
              <p>No anomalies match the current filter.</p>
            </div>
          ) : (
            <div className="anm-list">
              {filtered.map((anomaly) => (
                <AnomalyCard
                  key={anomaly.anomaly_id}
                  anomaly={anomaly}
                  open={expanded.has(anomaly.anomaly_id)}
                  onToggle={() => toggleExpand(anomaly.anomaly_id)}
                />
              ))}
            </div>
          )}

          <p className="anm-generated-at">
            Scanned {new Date(data.generated_at).toLocaleString()}
          </p>
        </>
      )}

      {/* ── Empty state before first scan ─────────────────────────── */}
      {!data && !loading && !error && (
        <div className="anm-pre-scan">
          <span className="anm-pre-scan-icon">🔎</span>
          <p>Click <strong>Run Scan</strong> to analyse both policies for anomalies and flag anything that deviates from insurance industry norms.</p>
        </div>
      )}
    </div>
  )
}

// ── SummaryBar ───────────────────────────────────────────────────────────────

function SummaryBar({ summary, policy1Name, policy2Name, filter, onFilter }) {
  const tabs = [
    { key: 'all',      label: `All (${summary.total_anomalies})` },
    { key: 'critical', label: `🚨 Critical (${summary.critical_count})` },
    { key: 'warning',  label: `⚠️ Warning (${summary.warning_count})` },
    { key: 'info',     label: `ℹ️ Info (${summary.info_count})` },
  ]

  const riskiestName =
    summary.riskiest_policy === 'policy1' ? policy1Name
    : summary.riskiest_policy === 'policy2' ? policy2Name
    : null

  return (
    <div className="anm-summary">
      {/* Stats pills */}
      <div className="anm-stat-row">
        <StatPill value={summary.critical_count} label="Critical" cls="anm-stat-critical" />
        <StatPill value={summary.warning_count}  label="Warnings" cls="anm-stat-warning"  />
        <StatPill value={summary.info_count}     label="Info"     cls="anm-stat-info"     />
        <StatPill value={summary.policy1_anomalies} label="Policy 1" cls="anm-stat-p1" />
        <StatPill value={summary.policy2_anomalies} label="Policy 2" cls="anm-stat-p2" />
      </div>

      {/* Riskiest policy callout */}
      {summary.riskiest_policy && summary.riskiest_policy !== 'equal' && (
        <div className="anm-riskiest">
          <span className="anm-riskiest-icon">⚡</span>
          <span>
            <strong>{riskiestName}</strong> has more critical/warning anomalies
            and carries higher risk.
          </span>
        </div>
      )}
      {summary.riskiest_policy === 'equal' && summary.total_anomalies > 0 && (
        <div className="anm-riskiest anm-riskiest-equal">
          <span className="anm-riskiest-icon">⚖️</span>
          <span>Both policies carry an equal level of flagged risk.</span>
        </div>
      )}

      {/* Filter tabs */}
      <div className="anm-filter-tabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={filter === t.key}
            className={`anm-filter-tab ${filter === t.key ? 'anm-filter-tab-active' : ''}`}
            onClick={() => onFilter(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function StatPill({ value, label, cls }) {
  return (
    <div className={`anm-stat-pill ${cls}`}>
      <span className="anm-stat-value">{value}</span>
      <span className="anm-stat-label">{label}</span>
    </div>
  )
}

// ── AnomalyCard ──────────────────────────────────────────────────────────────

function AnomalyCard({ anomaly, open, onToggle }) {
  const sev    = SEVERITY_META[anomaly.severity]  ?? SEVERITY_META.info
  const pol    = POLICY_META[anomaly.policy]      ?? POLICY_META.general
  const det    = DETECTED_BY_META[anomaly.detected_by] ?? DETECTED_BY_META.rule
  const catIcon = CATEGORY_ICONS[anomaly.category] ?? '📌'

  return (
    <div className={`anm-anomaly-card anm-anomaly-${anomaly.severity}`}>
      {/* Card header — always visible */}
      <div
        className="anm-anomaly-header"
        onClick={onToggle}
        role="button"
        aria-expanded={open}
      >
        <span className="anm-anomaly-sev-icon">{sev.icon}</span>
        <div className="anm-anomaly-header-mid">
          <span className="anm-anomaly-title">{anomaly.title}</span>
          <div className="anm-anomaly-chips">
            <span className={`anm-chip ${sev.cls}`}>{sev.label}</span>
            <span className={`anm-chip ${pol.cls}`}>{pol.label}</span>
            <span className="anm-chip anm-chip-cat">{catIcon} {anomaly.category}</span>
            <span className={`anm-chip ${det.cls}`}>{det.label}</span>
          </div>
        </div>
        <span className="anm-chevron">{open ? '▲' : '▼'}</span>
      </div>

      {/* Card body — expanded */}
      {open && (
        <div className="anm-anomaly-body">
          <p className="anm-anomaly-desc">{anomaly.description}</p>

          <div className="anm-anomaly-evidence">
            <span className="anm-evidence-label">Evidence</span>
            <code className="anm-evidence-value">{anomaly.evidence}</code>
          </div>

          <div className="anm-anomaly-suggestion">
            <span className="anm-suggestion-icon">💡</span>
            <span>{anomaly.suggestion}</span>
          </div>
        </div>
      )}
    </div>
  )
}
