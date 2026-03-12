import { useEffect, useState } from 'react'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, ArcElement,
  Tooltip, Legend, Title,
} from 'chart.js'
import { Bar, Doughnut } from 'react-chartjs-2'
import { getVisualisation } from '../services/api.js'
import './PolicyCharts.css'

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend, Title)

const PRIMARY   = '#a78bfa'
const POLICY1   = '#38bdf8'
const POLICY2   = '#f472b6'
const SURFACE   = '#1e1e1e'
const TEXT      = '#f0efe0'
const GRID      = 'rgba(240,239,224,0.08)'
const ACCENT    = '#818cf8'

function baseBarOpts(title, horizontal = false) {
  return {
    indexAxis: horizontal ? 'y' : 'x',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: TEXT, font: { size: 12 } } },
      title:  { display: !!title, text: title, color: TEXT, font: { size: 14, weight: 'bold' } },
      tooltip: { backgroundColor: '#1e1b4b', titleColor: PRIMARY, bodyColor: TEXT },
    },
    scales: {
      x: { ticks: { color: TEXT }, grid: { color: GRID } },
      y: { ticks: { color: TEXT }, grid: { color: GRID } },
    },
  }
}

function baseDonutOpts(title) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom', labels: { color: TEXT, font: { size: 11 }, padding: 12 } },
      title:  { display: !!title, text: title, color: TEXT, font: { size: 14, weight: 'bold' } },
      tooltip: { backgroundColor: '#1e1b4b', titleColor: PRIMARY, bodyColor: TEXT },
    },
  }
}

const DONUT_PALETTE = [
  '#38bdf8', '#f472b6', '#34d399', '#fb923c',
  '#a78bfa', '#facc15', '#f87171', '#22d3ee',
]

export default function PolicyCharts({ comparisonId }) {
  const [vis, setVis]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  useEffect(() => {
    setLoading(true)
    getVisualisation(comparisonId)
      .then(setVis)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [comparisonId])

  if (loading) return (
    <div className="pc-wrap">
      <div className="spinner-wrap"><div className="spinner" /><p>Loading charts…</p></div>
    </div>
  )

  if (error) return (
    <div className="pc-wrap">
      <div className="alert alert-error" role="alert">Charts unavailable: {error}</div>
    </div>
  )

  if (!vis) return null

  const { policy1_name, policy2_name, coverage_bar, coverage_donut,
          exclusions_donut, premium_bar, similarity_histogram } = vis

  /* ── Coverage grouped bar ── */
  const coverageBarData = {
    labels: coverage_bar.labels,
    datasets: [
      { label: policy1_name, data: coverage_bar.policy1_values, backgroundColor: POLICY1, borderRadius: 4 },
      { label: policy2_name, data: coverage_bar.policy2_values, backgroundColor: POLICY2, borderRadius: 4 },
    ],
  }

  /* ── Coverage donut ── */
  const coverageDonutData = {
    labels: coverage_donut.labels,
    datasets: [{ data: coverage_donut.values, backgroundColor: DONUT_PALETTE, borderWidth: 0 }],
  }

  /* ── Exclusions donut ── */
  const exclusionsDonutData = {
    labels: exclusions_donut.labels,
    datasets: [{ data: exclusions_donut.values, backgroundColor: DONUT_PALETTE, borderWidth: 0 }],
  }

  /* ── Premium bar ── */
  const allPremiumValues = [...premium_bar.policy1_values, ...premium_bar.policy2_values]
  const premiumMax = Math.max(...allPremiumValues)
  const hasPremiumData = premiumMax > 0

  const premiumBarData = {
    labels: premium_bar.labels,
    datasets: [
      { label: policy1_name, data: premium_bar.policy1_values, backgroundColor: POLICY1, borderRadius: 4 },
      { label: policy2_name, data: premium_bar.policy2_values, backgroundColor: POLICY2, borderRadius: 4 },
    ],
  }

  const premiumBarOpts = {
    ...baseBarOpts(''),
    scales: {
      x: { ticks: { color: TEXT }, grid: { color: GRID } },
      y: {
        ticks: { color: TEXT },
        grid: { color: GRID },
        suggestedMin: 0,
        suggestedMax: premiumMax > 0 ? premiumMax * 1.1 : 100,
      },
    },
  }

  /* ── Similarity histogram ── */
  const totalSimItems = similarity_histogram.counts.reduce((a, b) => a + b, 0)
  const hasSimData = totalSimItems > 0

  const simHistData = {
    labels: similarity_histogram.buckets,
    datasets: [{
      label: 'Section count',
      data: similarity_histogram.counts,
      backgroundColor: similarity_histogram.counts.map((_, i) => {
        const palette = ['#38bdf8','#818cf8','#a78bfa','#f472b6','#fb923c','#facc15','#34d399','#22d3ee']
        return palette[i % palette.length]
      }),
      borderColor: ACCENT,
      borderWidth: 1,
      borderRadius: 4,
    }],
  }

  return (
    <div className="pc-wrap">
      <h2 className="pc-heading">Policy Visualisations</h2>

      <div className="pc-grid">
        {/* Row 1: Coverage bar + Premium bar */}
        <div className="pc-card pc-wide">
          <h3 className="pc-card-title">Coverage Match by Section</h3>
          <div className="pc-chart-box">
            <Bar data={coverageBarData} options={baseBarOpts('')} />
          </div>
        </div>

        <div className="pc-card pc-wide">
          <h3 className="pc-card-title">Premium Comparison</h3>
          <div className="pc-chart-box">
            {hasPremiumData
              ? <Bar data={premiumBarData} options={premiumBarOpts} />
              : <div className="pc-empty">No premium amounts were detected in these policy documents.</div>
            }
          </div>
        </div>

        {/* Row 2: Coverage donut + Exclusions donut */}
        <div className="pc-card">
          <h3 className="pc-card-title">Coverage Distribution</h3>
          <div className="pc-chart-box pc-donut-box">
            <Doughnut data={coverageDonutData} options={baseDonutOpts('')} />
          </div>
        </div>

        <div className="pc-card">
          <h3 className="pc-card-title">Exclusions Distribution</h3>
          <div className="pc-chart-box pc-donut-box">
            <Doughnut data={exclusionsDonutData} options={baseDonutOpts('')} />
          </div>
        </div>

        {/* Row 3: Similarity histogram full-width */}
        <div className="pc-card pc-full">
          <h3 className="pc-card-title">Section Similarity Distribution</h3>
          <div className="pc-chart-box">
            {hasSimData ? (
              <Bar data={simHistData} options={{
                ...baseBarOpts(''),
                plugins: {
                  ...baseBarOpts('').plugins,
                  tooltip: {
                    ...baseBarOpts('').plugins.tooltip,
                    callbacks: {
                      title: (items) => `Similarity range: ${items[0].label}`,
                      label: (item) => `${item.raw} section${item.raw !== 1 ? 's' : ''}`,
                    },
                  },
                },
                scales: {
                  x: { ticks: { color: TEXT }, grid: { color: GRID } },
                  y: {
                    ticks: { color: TEXT, precision: 0 },
                    grid: { color: GRID },
                    suggestedMin: 0,
                    suggestedMax: Math.max(...similarity_histogram.counts, 1) + 1,
                  },
                },
              }} />
            ) : (
              <div className="pc-empty">No coverage sections were found to analyse similarity for these policies.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
