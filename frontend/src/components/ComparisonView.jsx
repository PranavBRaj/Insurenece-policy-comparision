import { useState } from 'react'
import CoverageSection from './CoverageSection.jsx'
import ExclusionsSection from './ExclusionsSection.jsx'
import PremiumSection from './PremiumSection.jsx'
import SummaryBanner from './SummaryBanner.jsx'
import './ComparisonView.css'

export default function ComparisonView({ data }) {
  if (!data) return null

  const { comparison_result, policy1_id, policy2_id } = data

  if (!comparison_result) {
    return (
      <div className="alert alert-error">
        No comparison result available. The analysis may have failed.
      </div>
    )
  }

  const { coverage, exclusions, premiums, summary, policy1_filename, policy2_filename } =
    comparison_result

  const p1name = policy1_filename || `Policy ${policy1_id}`
  const p2name = policy2_filename || `Policy ${policy2_id}`

  return (
    <div className="comparison-view">
      {/* Header row with policy names */}
      <div className="policy-header-row">
        <div className="policy-header p1-header">
          <span className="ph-badge badge badge-blue">Policy 1</span>
          <span className="ph-name">{p1name}</span>
        </div>
        <div className="vs-label">
          <span className="vs-inner">VS</span>
        </div>
        <div className="policy-header p2-header">
          <span className="ph-badge badge badge-violet">Policy 2</span>
          <span className="ph-name">{p2name}</span>
        </div>
      </div>

      {/* Summary banner */}
      {summary && <SummaryBanner summary={summary} p1name={p1name} p2name={p2name} />}

      {/* Tabbed Sections */}
      <TabbedSections
        coverage={coverage}
        exclusions={exclusions}
        premiums={premiums}
        p1name={p1name}
        p2name={p2name}
      />
    </div>
  )
}

const TABS = [
  { key: 'coverage',   label: 'Coverage',  icon: '🛡️' },
  { key: 'exclusions', label: 'Exclusions', icon: '🚫' },
  { key: 'premiums',   label: 'Premiums',   icon: '💰' },
]

function TabbedSections({ coverage, exclusions, premiums, p1name, p2name }) {
  const [active, setActive] = useState('coverage')

  return (
    <div className="cv-tabbed">
      <div className="cv-tab-bar" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={active === tab.key}
            className={`cv-tab ${active === tab.key ? 'cv-tab-active' : ''}`}
            onClick={() => setActive(tab.key)}
          >
            <span className="cv-tab-icon">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="cv-tab-panel" role="tabpanel">
        {active === 'coverage'   && <CoverageSection   data={coverage}   p1name={p1name} p2name={p2name} />}
        {active === 'exclusions' && <ExclusionsSection data={exclusions} p1name={p1name} p2name={p2name} />}
        {active === 'premiums'   && <PremiumSection    data={premiums}   p1name={p1name} p2name={p2name} />}
      </div>
    </div>
  )
}
