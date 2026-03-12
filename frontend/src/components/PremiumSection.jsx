import './PremiumSection.css'

const FIELD_LABELS = {
  annual_premium:    { label: 'Annual Premium',         icon: '📅' },
  monthly_premium:   { label: 'Monthly Premium',        icon: '🗓️' },
  deductible:        { label: 'Deductible',             icon: '💳' },
  copay:             { label: 'Co-pay',                 icon: '🏥' },
  coinsurance:       { label: 'Co-insurance',           icon: '📊' },
  out_of_pocket_max: { label: 'Out-of-Pocket Maximum',  icon: '🔒' },
}

export default function PremiumSection({ data, p1name, p2name }) {
  if (!data) return null

  const { policy1 = {}, policy2 = {}, differences = [] } = data

  const hasAnyValue = Object.keys(FIELD_LABELS).some(
    (k) => policy1[k] || policy2[k]
  )

  const hasAdditional =
    (policy1.additional_fees?.length > 0) || (policy2.additional_fees?.length > 0)

  return (
    <section className="premium-section card">
      <div className="ps-header">
        <h2 className="ps-title">💰 Premiums &amp; Costs</h2>
        {differences.length > 0 && (
          <span className="badge badge-yellow">{differences.length} difference{differences.length > 1 ? 's' : ''}</span>
        )}
      </div>

      {!hasAnyValue ? (
        <p className="ps-empty">No premium information could be extracted from these documents.</p>
      ) : (
        <>
          <div className="ps-table-wrap">
            <table className="ps-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th className="col-p1">{p1name}</th>
                  <th className="col-p2">{p2name}</th>
                  <th>Diff?</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(FIELD_LABELS).map(([key, { label, icon }]) => {
                  const v1 = policy1[key]
                  const v2 = policy2[key]
                  if (!v1 && !v2) return null
                  const differs = v1 && v2 && v1 !== v2
                  return (
                    <tr key={key} className={differs ? 'row-differs' : ''}>
                      <td className="field-label">{icon} {label}</td>
                      <td className="col-p1">
                        {v1
                          ? <span className="premium-val">{v1}</span>
                          : <span className="na-val">N/A</span>}
                      </td>
                      <td className="col-p2">
                        {v2
                          ? <span className="premium-val">{v2}</span>
                          : <span className="na-val">N/A</span>}
                      </td>
                      <td className="diff-cell">
                        {differs
                          ? <span className="badge badge-yellow">Different</span>
                          : v1 && v2
                            ? <span className="badge badge-green">Same</span>
                            : <span className="badge badge-gray">—</span>}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Additional fees */}
          {hasAdditional && (
            <div className="additional-fees">
              <p className="af-label">Additional amounts found in documents</p>
              <div className="af-cols">
                <AdditionalFees items={policy1.additional_fees} name={p1name} colorClass="p1" />
                <AdditionalFees items={policy2.additional_fees} name={p2name} colorClass="p2" />
              </div>
            </div>
          )}

          {/* Difference summary */}
          {differences.length > 0 && (
            <div className="ps-diffs">
              <p className="diffs-label">Key Differences</p>
              <ul className="diffs-list">
                {differences.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  )
}

function AdditionalFees({ items, name, colorClass }) {
  if (!items?.length) return null
  return (
    <div className={`af-col af-${colorClass}`}>
      <p className="af-col-header">{name}</p>
      <ul className="af-list">
        {items.map((item, i) => (
          <li key={i}>
            <span>{item.label}</span>
            <span className="premium-val">{item.amount}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
