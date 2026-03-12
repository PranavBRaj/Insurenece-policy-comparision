import { useState } from 'react'
import { getPlainSummary } from '../services/api.js'
import './PolicyPlainSummary.css'

// ── Constants ────────────────────────────────────────────────────────────────

const WINNER_META = {
  policy1: { icon: '🏆', cls: 'pps-winner-p1', label: 'Policy 1 Wins' },
  policy2: { icon: '🏆', cls: 'pps-winner-p2', label: 'Policy 2 Wins' },
  tie:     { icon: '🤝', cls: 'pps-winner-tie', label: 'It\'s a Tie' },
}

// ── Sub-components ───────────────────────────────────────────────────────────

function WinnerBadge({ value, label }) {
  const meta = WINNER_META[value] || WINNER_META.tie
  return (
    <span className={`pps-winner-badge ${meta.cls}`}>
      {meta.icon} {label}: {meta.label}
    </span>
  )
}

function PolicyCard({ summary, policyLabel }) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="pps-policy-card">
      <button
        className="pps-policy-header"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="pps-policy-label">{policyLabel}</span>
        <span className="pps-policy-name">{summary.policy_name}</span>
        <span className="pps-chevron">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="pps-policy-body">
          <p className="pps-one-liner">{summary.one_liner}</p>

          <div className="pps-section">
            <h4 className="pps-section-title">✅ What it covers</h4>
            <p>{summary.what_it_covers}</p>
          </div>

          <div className="pps-section">
            <h4 className="pps-section-title">🚫 What it doesn't cover</h4>
            <p>{summary.what_it_doesnt_cover}</p>
          </div>

          <div className="pps-section">
            <h4 className="pps-section-title">💰 How much it costs</h4>
            <p>{summary.cost_plain}</p>
          </div>

          <div className="pps-strengths-row">
            <div className="pps-strength">
              <span className="pps-strength-icon pps-icon-good">👍</span>
              <div>
                <p className="pps-strength-label">Biggest Strength</p>
                <p>{summary.biggest_strength}</p>
              </div>
            </div>
            <div className="pps-strength">
              <span className="pps-strength-icon pps-icon-bad">👎</span>
              <div>
                <p className="pps-strength-label">Biggest Weakness</p>
                <p>{summary.biggest_weakness}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ComparisonSummaryPanel({ cs, p1Name, p2Name }) {
  return (
    <div className="pps-comparison-panel">
      <p className="pps-executive">{cs.executive_summary}</p>

      <div className="pps-key-diff">
        <span className="pps-key-diff-label">Key difference</span>
        <p>{cs.key_difference}</p>
      </div>

      <div className="pps-compare-grid">
        <div className="pps-compare-item">
          <h4>💵 Cost</h4>
          <p>{cs.cost_comparison}</p>
          <WinnerBadge value={cs.who_wins_cost} label="Cost Winner" />
        </div>
        <div className="pps-compare-item">
          <h4>🛡️ Coverage</h4>
          <p>{cs.coverage_comparison}</p>
          <WinnerBadge value={cs.who_wins_coverage} label="Coverage Winner" />
        </div>
      </div>

      <div className="pps-bottom-line">
        <span className="pps-bottom-line-icon">💡</span>
        <div>
          <p className="pps-bottom-line-label">Bottom Line</p>
          <p>{cs.bottom_line}</p>
        </div>
      </div>

      <div className="pps-overall-row">
        <WinnerBadge value={cs.who_wins_overall} label="Overall Winner" />
        <span className="pps-read-time">
          📖 ~{Math.ceil(cs.reading_time_seconds / 60)} min read
        </span>
      </div>
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────

export default function PolicyPlainSummary({ comparisonId }) {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)
  const [data,    setData]    = useState(null)

  async function handleRun() {
    setError(null)
    setData(null)
    setLoading(true)
    try {
      const result = await getPlainSummary(comparisonId)
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="pps-card section-card">
      <div className="pps-header">
        <span className="pps-header-icon">📖</span>
        <div className="pps-header-text">
          <h2 className="pps-title">Plain-English Summary</h2>
          <p className="pps-subtitle">
            A consumer-friendly breakdown written for someone with no insurance expertise
          </p>
        </div>
        {!data && (
          <button
            className="btn btn-primary pps-run-btn"
            onClick={handleRun}
            disabled={loading}
          >
            {loading
              ? <><span className="btn-spinner" /> Generating…</>
              : '✨ Generate Summary'}
          </button>
        )}
      </div>

      {loading && (
        <div className="pps-loading">
          <div className="spinner" />
          <p>Writing your plain-English summary…</p>
        </div>
      )}

      {error && (
        <div className="alert alert-error" role="alert">
          <strong>Failed to generate summary:</strong> {error}
        </div>
      )}

      {data && (
        <div className="pps-content">
          <div className="pps-meta-bar">
            <span className="pps-meta-item">Grade 6 reading level</span>
            <span className="pps-meta-dot">·</span>
            <span className="pps-meta-item">{data.word_count} words</span>
            <span className="pps-meta-dot">·</span>
            <span className="pps-meta-item">
              ~{Math.ceil(data.comparison_summary.reading_time_seconds / 60)} min read
            </span>
            <button
              className="btn btn-ghost btn-sm pps-refresh-btn"
              onClick={handleRun}
              disabled={loading}
              title="Regenerate summary"
            >
              🔄 Regenerate
            </button>
          </div>

          <div className="pps-policies-grid">
            <PolicyCard summary={data.policy1_summary} policyLabel="Policy 1" />
            <PolicyCard summary={data.policy2_summary} policyLabel="Policy 2" />
          </div>

          <ComparisonSummaryPanel
            cs={data.comparison_summary}
            p1Name={data.policy1_name}
            p2Name={data.policy2_name}
          />
        </div>
      )}
    </section>
  )
}
