import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import LiveConsole from './pages/LiveConsole';
import RunHistory from './pages/RunHistory';
import VulnerabilityReport from './pages/VulnerabilityReport';
import InjectionScorer from './pages/InjectionScorer';
import DefenseComparison from './pages/DefenseComparison';
import Sidebar from './components/Sidebar';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-950 text-gray-100">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6">
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
