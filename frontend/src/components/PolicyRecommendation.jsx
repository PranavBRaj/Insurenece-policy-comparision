import { useState } from 'react'
import { getRecommendations } from '../services/api.js'
import './PolicyRecommendation.css'

// ── Constants ───────────────────────────────────────────────────────────────

const BUDGET_OPTIONS = [
  { value: '', label: 'Not specified' },
  { value: 'lowest_premium',    label: 'Lowest premium' },
  { value: 'lowest_deductible', label: 'Lowest deductible' },
  { value: 'maximum_coverage',  label: 'Maximum coverage' },
  { value: 'balanced',          label: 'Balanced (cost vs. coverage)' },
]

const CONCERN_OPTIONS = [
  { value: '', label: 'Not specified' },
  { value: 'hospitalization', label: 'Hospitalization' },
  { value: 'dental',          label: 'Dental' },
  { value: 'vision',          label: 'Vision' },
  { value: 'mental_health',   label: 'Mental health' },
  { value: 'prescription',    label: 'Prescription drugs' },
  { value: 'maternity',       label: 'Maternity / pregnancy' },
  { value: 'preventive',      label: 'Preventive care' },
  { value: 'general',         label: 'General / comprehensive' },
]

const RISK_OPTIONS = [
  { value: '',       label: 'Not specified' },
  { value: 'low',    label: 'Low  (prefer certainty, low deductible)' },
  { value: 'medium', label: 'Medium' },
  { value: 'high',   label: 'High  (OK with higher deductible for lower premium)' },
]

const CONFIDENCE_META = {
  high:   { label: 'High confidence',   cls: 'rec-conf-high'   },
  medium: { label: 'Medium confidence', cls: 'rec-conf-medium' },
  low:    { label: 'Low confidence',    cls: 'rec-conf-low'    },
}

const WINNER_LABELS = {
  policy1: { icon: '🏆', cls: 'rec-winner-p1' },
  policy2: { icon: '🏆', cls: 'rec-winner-p2' },
  tie:     { icon: '🤝', cls: 'rec-winner-tie' },
}

const POLICY_BADGE = {
  policy1:  { label: 'Policy 1', cls: 'rec-badge-p1'  },
  policy2:  { label: 'Policy 2', cls: 'rec-badge-p2'  },
  either:   { label: 'Either',   cls: 'rec-badge-either' },
  neither:  { label: 'Neither',  cls: 'rec-badge-neither' },
}

// ── Main component ───────────────────────────────────────────────────────────

export default function PolicyRecommendation({ comparisonId }) {
  const [form, setForm]       = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [result, setResult]   = useState(null)
  const [expanded, setExpanded] = useState(null) // which alt-profile card is open

  function setField(key, value) {
    setForm((prev) => {
      const next = { ...prev }
      if (value === '' || value === null || value === undefined) {
        delete next[key]
      } else {
        next[key] = value
      }
      return next
    })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const data = await getRecommendations(comparisonId, form)
      setResult(data)
      setExpanded(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="prec-card card">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="prec-header">
        <span className="prec-header-icon">🎯</span>
        <div>
          <h3 className="prec-title">Policy Recommendation</h3>
          <p className="prec-subtitle">
            Tell us about yourself and get a personalised policy recommendation powered by AI
          </p>
        </div>
      </div>

      {/* ── Profile form ────────────────────────────────────────── */}
      <form className="prec-form" onSubmit={handleSubmit}>
        <p className="prec-form-note">All fields are optional — fill in whatever applies to you.</p>

        <div className="prec-grid">
          {/* Age */}
          <label className="prec-field">
            <span className="prec-label">Age</span>
            <input
              type="number"
              className="prec-input"
              placeholder="e.g. 32"
              min={18}
              max={100}
              value={form.age ?? ''}
              onChange={(e) => setField('age', e.target.value ? parseInt(e.target.value, 10) : '')}
            />
          </label>

          {/* Family size */}
          <label className="prec-field">
            <span className="prec-label">Family size</span>
            <input
              type="number"
              className="prec-input"
              placeholder="No. of people incl. yourself"
              min={1}
              max={20}
              value={form.family_size ?? ''}
              onChange={(e) => setField('family_size', e.target.value ? parseInt(e.target.value, 10) : '')}
            />
          </label>

          {/* Budget priority */}
          <label className="prec-field">
            <span className="prec-label">Budget priority</span>
            <select
              className="prec-select"
              value={form.budget_priority ?? ''}
              onChange={(e) => setField('budget_priority', e.target.value)}
            >
              {BUDGET_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>

          {/* Primary concern */}
          <label className="prec-field">
            <span className="prec-label">Primary concern</span>
            <select
              className="prec-select"
              value={form.primary_concern ?? ''}
              onChange={(e) => setField('primary_concern', e.target.value)}
            >
              {CONCERN_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>

          {/* Risk tolerance */}
          <label className="prec-field">
            <span className="prec-label">Risk tolerance</span>
            <select
              className="prec-select"
              value={form.risk_tolerance ?? ''}
              onChange={(e) => setField('risk_tolerance', e.target.value)}
            >
              {RISK_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
        </div>

        {/* Checkboxes */}
        <div className="prec-checks">
          <CheckField
            id="has_children"
            label="Have children / dependants"
            checked={form.has_children ?? false}
            onChange={(v) => setField('has_children', v || '')}
          />
          <CheckField
            id="is_senior"
            label="Senior / retired (age 65+)"
            checked={form.is_senior ?? false}
            onChange={(v) => setField('is_senior', v || '')}
          />
          <CheckField
            id="has_chronic_condition"
            label="Have a chronic / ongoing health condition"
            checked={form.has_chronic_condition ?? false}
            onChange={(v) => setField('has_chronic_condition', v || '')}
          />
        </div>

        {/* Notes */}
        <label className="prec-field prec-field-full">
          <span className="prec-label">Additional notes <span className="prec-optional">(max 300 chars)</span></span>
          <textarea
            className="prec-textarea"
            placeholder="Any other details that might be relevant…"
            rows={2}
            maxLength={300}
            value={form.notes ?? ''}
            onChange={(e) => setField('notes', e.target.value)}
          />
        </label>

        <button
          type="submit"
          className="btn btn-primary prec-submit-btn"
          disabled={loading}
        >
          {loading
            ? <><span className="btn-spinner" /> Analysing policies…</>
            : <>🎯 Get My Recommendation</>}
        </button>
      </form>

      {/* ── Error ───────────────────────────────────────────────── */}
      {error && (
        <div className="alert alert-error" role="alert">
          <strong>Recommendation failed:</strong> {error}
        </div>
      )}

      {/* ── Results ─────────────────────────────────────────────── */}
      {result && (
        <div className="prec-results">
          {/* Overall winner */}
          <OverallWinner result={result} />

          {/* Primary recommendation */}
          <div className="prec-section-label">Your personalised recommendation</div>
          <ProfileCard profile={result.primary_recommendation} highlight />

          {/* Alternative profiles */}
          <div className="prec-section-label">How each policy suits common profiles</div>
          <div className="prec-alt-grid">
            {result.alternative_profiles.map((p, i) => (
              <ProfileCard
                key={i}
                profile={p}
                collapsible
                open={expanded === i}
                onToggle={() => setExpanded(expanded === i ? null : i)}
              />
            ))}
          </div>

          <p className="prec-generated-at">
            Generated {new Date(result.generated_at).toLocaleString()}
          </p>
        </div>
      )}
    </div>
  )
}

// ── Sub-components ───────────────────────────────────────────────────────────

function CheckField({ id, label, checked, onChange }) {
  return (
    <label className="prec-check-label" htmlFor={id}>
      <input
        id={id}
        type="checkbox"
        className="prec-checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked ? true : false)}
      />
      {label}
    </label>
  )
}

function OverallWinner({ result }) {
  const { overall_winner, overall_winner_name, policy1_name, policy2_name } = result
  if (!overall_winner) return null
  const meta = WINNER_LABELS[overall_winner] ?? WINNER_LABELS.tie
  return (
    <div className={`prec-winner-banner ${meta.cls}`}>
      <span className="prec-winner-icon">{meta.icon}</span>
      <div className="prec-winner-text">
        <span className="prec-winner-label">Overall Winner</span>
        <span className="prec-winner-name">
          {overall_winner === 'tie'
            ? `${policy1_name} and ${policy2_name} are tied`
            : overall_winner_name}
        </span>
        <span className="prec-winner-sub">
          Based on majority vote across all profiles
        </span>
      </div>
    </div>
  )
}

function ProfileCard({ profile, highlight = false, collapsible = false, open = false, onToggle }) {
  const badge  = POLICY_BADGE[profile.recommended_policy] ?? POLICY_BADGE.either
  const conf   = CONFIDENCE_META[profile.confidence]        ?? CONFIDENCE_META.low
  const isOpen = !collapsible || open

  return (
    <div className={`prec-profile-card ${highlight ? 'prec-profile-highlight' : ''}`}>
      {/* Card header */}
      <div
        className={`prec-profile-header ${collapsible ? 'prec-profile-header-toggle' : ''}`}
        onClick={collapsible ? onToggle : undefined}
        role={collapsible ? 'button' : undefined}
        aria-expanded={collapsible ? open : undefined}
      >
        <div className="prec-profile-meta">
          <span className="prec-profile-label">{profile.profile_label}</span>
          <div className="prec-profile-badges">
            <span className={`prec-badge ${badge.cls}`}>{badge.label}</span>
            <span className={`prec-conf ${conf.cls}`}>{conf.label}</span>
          </div>
        </div>
        <div className="prec-profile-right">
          <span className="prec-policy-name">{profile.recommended_policy_name}</span>
          {collapsible && (
            <span className="prec-chevron">{open ? '▲' : '▼'}</span>
          )}
        </div>
      </div>

      {/* Card body */}
      {isOpen && (
        <div className="prec-profile-body">
          <p className="prec-reasoning">{profile.reasoning}</p>

          {profile.key_factors?.length > 0 && (
            <div className="prec-factors">
              <span className="prec-factors-label">Key factors</span>
              <ul className="prec-factors-list">
                {profile.key_factors.map((f, i) => (
                  <li key={i} className="prec-factor-item">
                    <span className="prec-bullet">✦</span> {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {profile.caveats?.length > 0 && (
            <div className="prec-caveats">
              <span className="prec-caveats-label">⚠ Caveats</span>
              <ul className="prec-caveats-list">
                {profile.caveats.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
