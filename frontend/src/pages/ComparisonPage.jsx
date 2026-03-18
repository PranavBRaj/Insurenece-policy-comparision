import { useEffect, useState } from 'react'
import { useParams, useLocation, Link, Outlet, useOutletContext } from 'react-router-dom'
import ComparisonView from '../components/ComparisonView.jsx'
import PolicyAnomalies from '../components/PolicyAnomalies.jsx'
import PolicyCharts from '../components/PolicyCharts.jsx'
import PolicyPlainSummary from '../components/PolicyPlainSummary.jsx'
import PolicyQA from '../components/PolicyQA.jsx'
import PolicyRecommendation from '../components/PolicyRecommendation.jsx'
import { getComparison, downloadPdf } from '../services/api.js'
import './ComparisonPage.css'

export default function ComparisonPage() {
  const { id } = useParams()
  const location = useLocation()

  const [data, setData]           = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError]   = useState(null)

  useEffect(() => {
    const routeData = location.state?.result?.comparison
    if (routeData && String(routeData.id) === String(id)) {
      setData(routeData)
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    getComparison(id)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [id, location.state])

  async function handleDownloadPdf() {
    setPdfError(null)
    setPdfLoading(true)
    try {
      await downloadPdf(id)
    } catch (err) {
      setPdfError(err.message)
    } finally {
      setPdfLoading(false)
    }
  }

  return (
    <div className="comparison-page">
      <div className="cp-breadcrumb">
        <Link to="/">← New Comparison</Link>
        <span className="cp-sep">/</span>
        <span>Comparison #{id}</span>
      </div>

      {loading && (
        <div className="spinner-wrap">
          <div className="spinner" />
          <p>Loading comparison results…</p>
        </div>
      )}

      {error && (
        <div className="alert alert-error" role="alert">
          <strong>Failed to load comparison:</strong> {error}
        </div>
      )}

      {!loading && !error && data && (
        <>
          <div className="cp-meta">
            <div className="cp-meta-row">
              <span className={`badge badge-${statusBadge(data.status)}`}>
                {data.status}
              </span>
              <span className="cp-date">
                {new Date(data.created_at).toLocaleString()}
              </span>
              <button
                className="btn btn-primary btn-sm cp-pdf-btn"
                onClick={handleDownloadPdf}
                disabled={pdfLoading}
                title="Download comparison as PDF"
              >
                {pdfLoading
                  ? <><span className="btn-spinner" /> Generating…</>
                  : <>⬇ Download PDF</>}
              </button>
            </div>
            {pdfError && (
              <div className="alert alert-error cp-pdf-error" role="alert">
                {pdfError}
              </div>
            )}
          </div>

          <Outlet context={{ comparisonId: id, data }} />
        </>
      )}
    </div>
  )
}

export function ComparisonOverviewPage() {
  const { data } = useOutletContext()
  return <ComparisonView data={data} />
}

export function ComparisonAnomaliesPage() {
  const { comparisonId } = useOutletContext()
  return <PolicyAnomalies comparisonId={comparisonId} />
}

export function ComparisonVisualsPage() {
  const { comparisonId } = useOutletContext()
  return <PolicyCharts comparisonId={comparisonId} />
}

export function ComparisonQAPage() {
  const { comparisonId } = useOutletContext()
  return <PolicyQA comparisonId={comparisonId} />
}

export function ComparisonRecommendationPage() {
  const { comparisonId } = useOutletContext()
  return <PolicyRecommendation comparisonId={comparisonId} />
}

export function ComparisonSummaryPage() {
  const { comparisonId } = useOutletContext()
  return <PolicyPlainSummary comparisonId={comparisonId} />
}

function statusBadge(status) {
  const map = { completed: 'green', failed: 'red', processing: 'yellow', pending: 'gray' }
  return map[status] || 'gray'
}
