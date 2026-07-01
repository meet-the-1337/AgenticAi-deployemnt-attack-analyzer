import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Zap, Shield, Terminal } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import LiveConsole from './pages/LiveConsole';

function Sidebar() {
  const location = useLocation();

  const navItem = (path, icon, label) => {
    const Icon = icon;
    const active = location.pathname === path;
    return (
      <Link to={path} className={active ? 'active' : ''}>
        <Icon size={18} />
        {label}
      </Link>
    );
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon">
          <Shield size={20} color="#fff" />
        </div>
        <h1>Recon<span>Mind</span></h1>
      </div>

      <div className="sidebar-section-label">Analytics</div>
      <nav className="sidebar-nav">
        {navItem('/', LayoutDashboard, 'Dashboard')}
      </nav>

      <div className="sidebar-section-label">Operations</div>
      <nav className="sidebar-nav">
        {navItem('/console', Terminal, 'Attack Console')}
      </nav>

      <div className="sidebar-footer">
        <div>
          <span className="status-dot"></span>
          <span className="status-text">Pipeline Online</span>
        </div>
        <div className="version">ReconMind v1.0 · Agentic Security</div>
      </div>
    </aside>
  );
}

function App() {
  return (
    <Router>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/console" element={<LiveConsole />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
