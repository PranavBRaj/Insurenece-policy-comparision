import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import HomePage from './pages/HomePage.jsx'
import ComparisonPage, {
  ComparisonAnomaliesPage,
  ComparisonOverviewPage,
  ComparisonQAPage,
  ComparisonRecommendationPage,
  ComparisonSummaryPage,
  ComparisonVisualsPage,
} from './pages/ComparisonPage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import './App.css'

const FUNCTION_TABS = [
  { path: 'overview', label: 'Overview' },
  { path: 'anomalies', label: 'Anomalies' },
  { path: 'visuals', label: 'Visuals' },
  { path: 'qa', label: 'Q&A' },
  { path: 'recommendation', label: 'Recommendation' },
  { path: 'summary', label: 'Summary' }
]

function Header({ theme, onToggleTheme }) {
  const location = useLocation()
  const comparisonMatch = location.pathname.match(/^\/comparison\/([^/]+)(?:\/([^/]+))?$/)
  const comparisonBase = comparisonMatch ? `/comparison/${comparisonMatch[1]}` : null
  const activeFeature = comparisonMatch?.[2] || 'overview'

  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="header-brand">
          <span className="brand-icon">🍝</span>
          <div className="brand-text">
            <span className="brand-name">PASTA</span>
            <span className="brand-tagline">Policy Analysis &amp; Summary Tool with AI</span>
          </div>
        </div>
        <div className="header-nav-wrap">
          <div className="header-top-controls">
            <nav className="header-nav">
              <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
                ⚡ Compare
              </NavLink>
              <NavLink to="/history" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
                📂 History
              </NavLink>
            </nav>
            <button
              type="button"
              className="theme-toggle"
              onClick={onToggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            >
              {theme === 'dark' ? '☀ Light' : '🌙 Dark'}
            </button>
          </div>
          {comparisonBase && (
            <nav className="header-function-nav" aria-label="Comparison functions">
              {FUNCTION_TABS.map((tab) => (
                <NavLink
                  key={tab.path}
                  to={`${comparisonBase}/${tab.path}`}
                  className={activeFeature === tab.path ? 'function-link active' : 'function-link'}
                >
                  {tab.label}
                </NavLink>
              ))}
            </nav>
          )}
        </div>
      </div>
    </header>
  )
}

export default function App() {
  const [theme, setTheme] = useState(() => {
    const savedTheme = window.localStorage.getItem('pasta-theme')
    return savedTheme === 'light' ? 'light' : 'dark'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    window.localStorage.setItem('pasta-theme', theme)
  }, [theme])

  function toggleTheme() {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  return (
    <BrowserRouter>
      <div className="app-root">
        <Header theme={theme} onToggleTheme={toggleTheme} />
        <main className="app-main">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/comparison/:id" element={<ComparisonPage />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<ComparisonOverviewPage />} />
              <Route path="anomalies" element={<ComparisonAnomaliesPage />} />
              <Route path="visuals" element={<ComparisonVisualsPage />} />
              <Route path="qa" element={<ComparisonQAPage />} />
              <Route path="recommendation" element={<ComparisonRecommendationPage />} />
              <Route path="summary" element={<ComparisonSummaryPage />} />
            </Route>
            <Route path="/history" element={<HistoryPage />} />
          </Routes>
        </main>
        <footer className="app-footer">
          <p><strong>PASTA</strong> &mdash; Policy Analysis and Summary Tool with AI &copy; {new Date().getFullYear()}</p>
        </footer>
      </div>
    </BrowserRouter>
  )
}
