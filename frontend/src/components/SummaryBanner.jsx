import './SummaryBanner.css'

export default function SummaryBanner({ summary, p1name, p2name }) {
  const {
    total_coverage_items_policy1: cov1,
    total_coverage_items_policy2: cov2,
    shared_coverage_items: shared,
    total_exclusion_items_policy1: exc1,
    total_exclusion_items_policy2: exc2,
    policy1_advantages: adv1 = [],
    policy2_advantages: adv2 = [],
  } = summary

  return (
    <div className="summary-banner card">
      <h3 className="summary-title">📊 Comparison Summary</h3>

      <div className="summary-stats">
        <StatCard label="Shared Coverage Items" value={shared} color="green" />
        <StatCard label={`${p1name} Coverage Items`}  value={cov1} color="blue"   />
        <StatCard label={`${p2name} Coverage Items`}  value={cov2} color="violet" />
        <StatCard label={`${p1name} Exclusion Items`} value={exc1} color="blue"   />
        <StatCard label={`${p2name} Exclusion Items`} value={exc2} color="violet" />
      </div>

      <div className="summary-advantages">
        {adv1.length > 0 && (
          <AdvantageBox title={`${p1name} advantages`} items={adv1} color="blue" />
        )}
        {adv2.length > 0 && (
          <AdvantageBox title={`${p2name} advantages`} items={adv2} color="violet" />
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div className={`stat-card stat-${color}`}>
      <span className="stat-value">{value ?? '—'}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}

function AdvantageBox({ title, items, color }) {
  return (
    <div className={`adv-box adv-${color}`}>
      <p className="adv-title">{title}</p>
      <ul className="adv-list">
        {items.map((item, i) => <li key={i}>{item}</li>)}
      </ul>
    </div>
  )
}
