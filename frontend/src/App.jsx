import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useState } from 'react';
import Dashboard from './pages/Dashboard';
import LiveConsole from './pages/LiveConsole';
import RunHistory from './pages/RunHistory';
import VulnerabilityReport from './pages/VulnerabilityReport';
import InjectionScorer from './pages/InjectionScorer';
import DefenseComparison from './pages/DefenseComparison';
import Sidebar from './components/Sidebar';

export default function App() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <BrowserRouter>
      <div style={{
        display: 'flex', height: '100vh', width: '100vw',
        background: '#020617', color: '#cbd5e1',
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        overflow: 'hidden',
      }}>
        <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
        <main style={{
          flex: 1, overflowY: 'auto', overflowX: 'hidden',
          background: 'linear-gradient(160deg, #020617 0%, #0a0f1f 50%, #0d1117 100%)',
          transition: 'margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/console" element={<LiveConsole />} />
            <Route path="/history" element={<RunHistory />} />
            <Route path="/vulnerability" element={<VulnerabilityReport />} />
            <Route path="/scores" element={<InjectionScorer />} />
            <Route path="/defense" element={<DefenseComparison />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
