import { useState } from 'react'
import './SectionTable.css'

/**
 * Reusable component that renders a three-part comparison table:
 *   – shared items (both policies)
 *   – items only in policy 1
 *   – items only in policy 2
 *
 * Props:
 *   title      – section heading
 *   icon       – emoji icon
 *   data       – { common[], only_in_policy1[], only_in_policy2[] }
 *   p1name     – name label for policy 1
 *   p2name     – name label for policy 2
 *   colorClass – 'coverage' | 'exclusions'
 */
export default function SectionTable({ title, icon, data, p1name, p2name, colorClass }) {
  const [showAll, setShowAll] = useState(false)
  if (!data) return null

  const { common = [], only_in_policy1 = [], only_in_policy2 = [] } = data
  const hasData = common.length + only_in_policy1.length + only_in_policy2.length > 0

  return (
    <section className={`section-table card ${colorClass}`}>
      <div className="st-header">
        <h2 className="st-title">{icon} {title}</h2>
        <div className="st-counts">
          <span className="badge badge-green">{common.length} shared</span>
          <span className="badge badge-blue">{only_in_policy1.length} only in P1</span>
          <span className="badge badge-violet">{only_in_policy2.length} only in P2</span>
        </div>
      </div>

      {!hasData ? (
        <p className="st-empty">No items extracted for this section.</p>
      ) : (
        <>
          {/* Shared items */}
          {common.length > 0 && (
            <div className="st-group">
              <p className="st-group-label shared-label">In Both Policies</p>
              <table className="st-tbl">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th className="col-p1">{p1name}</th>
                    <th className="col-p2">{p2name}</th>
                  </tr>
                </thead>
                <tbody>
                  {(showAll ? common : common.slice(0, 10)).map((item, i) => (
                    <tr key={i}>
                      <td className="item-text">{item.item}</td>
                      <td className="col-p1">
                        {item.policy1_amount
                          ? <span className="amount-chip">{item.policy1_amount}</span>
                          : <span className="detail-text">{truncate(item.policy1_details || '—')}</span>}
                      </td>
                      <td className="col-p2">
                        {item.policy2_amount
                          ? <span className="amount-chip">{item.policy2_amount}</span>
                          : <span className="detail-text">{truncate(item.policy2_details || '—')}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Unique to P1 / P2 side-by-side */}
          {(only_in_policy1.length > 0 || only_in_policy2.length > 0) && (
            <div className="st-group">
              <p className="st-group-label unique-label">Unique to Each Policy</p>
              <div className="unique-cols">
                <UniqueList items={only_in_policy1} label={p1name} colorClass="p1" />
                <UniqueList items={only_in_policy2} label={p2name} colorClass="p2" />
              </div>
            </div>
          )}

          {!showAll && (common.length > 10) && (
            <button className="btn btn-ghost show-more-btn" onClick={() => setShowAll(true)}>
              Show all {common.length} shared items ▼
            </button>
          )}
        </>
      )}
    </section>
  )
}

function UniqueList({ items, label, colorClass }) {
  const [more, setMore] = useState(false)
  const visible = more ? items : items.slice(0, 8)
  return (
    <div className={`unique-col unique-${colorClass}`}>
      <p className="unique-col-header">{label}</p>
      {items.length === 0
        ? <p className="st-empty-col">None</p>
        : (
          <>
            <ul className="unique-list">
              {visible.map((item, i) => (
                <li key={i} className="unique-item">
                  <span className="ui-text">{item.text}</span>
                  {item.amount && <span className="amount-chip">{item.amount}</span>}
                </li>
              ))}
            </ul>
            {!more && items.length > 8 && (
              <button className="show-more-inline" onClick={() => setMore(true)}>
                +{items.length - 8} more
              </button>
            )}
          </>
        )}
    </div>
  )
}

function truncate(str, len = 80) {
  if (!str) return '—'
  return str.length > len ? str.slice(0, len) + '…' : str
}
