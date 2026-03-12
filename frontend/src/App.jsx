import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import HomePage from './pages/HomePage.jsx'
import ComparisonPage from './pages/ComparisonPage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import './App.css'

function Header() {
  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="header-brand">
          <span className="brand-icon">📋</span>
          <span className="brand-name">PolicyLens</span>
        </div>
        <nav className="header-nav">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            ⚡ Compare
          </NavLink>
          <NavLink to="/history" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            📂 History
          </NavLink>
        </nav>
      </div>
    </header>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-root">
        <Header />
        <main className="app-main">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/comparison/:id" element={<ComparisonPage />} />
            <Route path="/history" element={<HistoryPage />} />
          </Routes>
        </main>
        <footer className="app-footer">
          <p>PolicyLens &mdash; Insurance Policy Comparator &copy; {new Date().getFullYear()}</p>
        </footer>
      </div>
    </BrowserRouter>
  )
}
