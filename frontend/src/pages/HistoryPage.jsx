import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getHistory, deleteComparison } from '../services/api.js'
import './HistoryPage.css'

export default function HistoryPage() {
  const [items, setItems]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [deleting, setDeleting] = useState(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const data = await getHistory()
      setItems(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(comparisonId) {
    if (!confirm('Delete this comparison? This cannot be undone.')) return
    setDeleting(comparisonId)
    try {
      await deleteComparison(comparisonId)
      setItems((prev) => prev.filter((i) => i.comparison_id !== comparisonId))
    } catch (err) {
      alert(`Delete failed: ${err.message}`)
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="history-page">
      <div className="hp-header">
        <h1 className="hp-title">Comparison History</h1>
        <Link to="/" className="btn btn-primary">+ New Comparison</Link>
      </div>

      {loading && (
        <div className="spinner-wrap"><div className="spinner" /><p>Loading history…</p></div>
      )}

      {error && <div className="alert alert-error">{error}</div>}

      {!loading && !error && items.length === 0 && (
        <div className="hp-empty card">
          <span className="hp-empty-icon">📂</span>
          <p>No comparisons yet.</p>
          <Link to="/" className="btn btn-primary" style={{ marginTop: 16 }}>
            Start your first comparison →
          </Link>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="history-table-wrap card">
          <table className="history-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Policy 1</th>
                <th>Policy 2</th>
                <th>Status</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td className="id-cell">{item.id}</td>
                  <td className="name-cell">{item.policy1_filename || '—'}</td>
                  <td className="name-cell">{item.policy2_filename || '—'}</td>
                  <td>
                    <span className={`badge badge-${statusBadge(item.status)}`}>
                      {item.status}
                    </span>
                  </td>
                  <td className="date-cell">
                    {new Date(item.created_at).toLocaleDateString()}{' '}
                    <span className="date-time">
                      {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </td>
                  <td className="actions-cell">
                    {item.comparison_id && item.status === 'completed' && (
                      <Link
                        to={`/comparison/${item.comparison_id}`}
                        className="btn btn-ghost btn-sm"
                      >
                        View
                      </Link>
                    )}
                    {item.comparison_id && (
                      <button
                        className="btn btn-danger btn-sm"
                        disabled={deleting === item.comparison_id}
                        onClick={() => handleDelete(item.comparison_id)}
                      >
                        {deleting === item.comparison_id ? '…' : 'Delete'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function statusBadge(status) {
  const map = { completed: 'green', failed: 'red', processing: 'yellow', uploading: 'blue', pending: 'gray' }
  return map[status] || 'gray'
}
