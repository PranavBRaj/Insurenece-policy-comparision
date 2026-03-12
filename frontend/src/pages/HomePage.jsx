import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FileUploader from '../components/FileUploader.jsx'
import { uploadAndCompare } from '../services/api.js'
import './HomePage.css'

export default function HomePage() {
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const navigate = useNavigate()

  async function handleCompare(file1, file2, setProgress) {
    setError(null)
    setLoading(true)
    try {
      const result = await uploadAndCompare(file1, file2, setProgress)
      navigate(`/comparison/${result.comparison.id}`, { state: { result } })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="home-page">
      {/* Hero Section */}
      <div className="home-hero">
        <div className="hero-badge">✨ AI-Powered Analysis</div>
        <h1 className="hero-title">
          Compare Insurance Policies<br />
          <span className="text-gradient">Instantly & Intelligently</span>
        </h1>
        <p className="hero-subtitle">
          Upload two policy documents and get a comprehensive side-by-side analysis
          of coverage, exclusions, and pricing — in seconds.
        </p>
        <div className="hero-stats">
          <div className="hero-stat"><strong>3</strong><span>Sections Analyzed</span></div>
          <div className="hero-stat-divider" />
          <div className="hero-stat"><strong>AI</strong><span>Powered Engine</span></div>
          <div className="hero-stat-divider" />
          <div className="hero-stat"><strong>100%</strong><span>Accurate Comparison</span></div>
        </div>
      </div>

      {/* Upload Card */}
      <div className="upload-card card">
        <div className="upload-card-header">
          <div className="upload-card-icon">📁</div>
          <div>
            <h2 className="upload-card-title">Upload Your Policy Documents</h2>
            <p className="upload-card-sub">Support for .txt policy files up to 5 MB</p>
          </div>
        </div>

        {error && (
          <div className="alert alert-error" role="alert">
            <span>⚠️</span>
            <div><strong>Error:</strong> {error}</div>
          </div>
        )}

        <FileUploader onCompare={handleCompare} loading={loading} />
      </div>

      {/* How It Works */}
      <div className="how-it-works">
        <div className="how-header">
          <span className="how-eyebrow">How it works</span>
          <h3 className="how-title">Three simple steps to clarity</h3>
        </div>
        <div className="steps">
          <Step num="1" icon="📤" title="Upload Documents" desc="Drag and drop or click to select your two insurance policy text files." />
          <Step num="2" icon="🔍" title="AI Extraction"  desc="Our engine parses coverage, exclusions, and premium data from each document." />
          <Step num="3" icon="📊" title="Side-by-side View" desc="Review a detailed comparison with differences clearly highlighted for you." />
        </div>
      </div>

      {/* Feature Highlights */}
      <div className="features-grid">
        <Feature icon="🛡️" title="Coverage Analysis" desc="Identify what each policy covers and find shared or unique coverage items." color="blue" />
        <Feature icon="🚫" title="Exclusions Mapping" desc="Spot exactly what's excluded to avoid surprises when you file a claim." color="red" />
        <Feature icon="💰" title="Cost Breakdown" desc="Compare premiums, deductibles, copays, and out-of-pocket maximums." color="amber" />
        <Feature icon="📂" title="History Tracking" desc="All your comparisons are saved so you can revisit them any time." color="violet" />
      </div>
    </div>
  )
}

function Step({ num, icon, title, desc }) {
  return (
    <div className="step">
      <div className="step-header">
        <div className="step-num">{num}</div>
        <span className="step-icon">{icon}</span>
      </div>
      <p className="step-title">{title}</p>
      <p className="step-desc">{desc}</p>
    </div>
  )
}

function Feature({ icon, title, desc, color }) {
  return (
    <div className={`feature-card feature-${color}`}>
      <span className="feature-icon">{icon}</span>
      <h4 className="feature-title">{title}</h4>
      <p className="feature-desc">{desc}</p>
    </div>
  )
}
