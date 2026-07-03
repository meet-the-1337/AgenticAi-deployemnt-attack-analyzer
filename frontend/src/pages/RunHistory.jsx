import React, { useState, useEffect } from 'react';
import { fetchRuns, fetchRunEvents, exportRunsCSV } from '../api/client';
import { History, Download, Filter, Clock, Search, X } from 'lucide-react';

const oc = (o) => o === 'full_success' ? '#f87171' : o === 'partial' ? '#fbbf24' : o === 'ignored' ? '#34d399' : '#60a5fa';
const sc = (s) => s === 'blatant' ? '#f87171' : s === 'moderate' ? '#fbbf24' : '#6b7280';

export default function RunHistory() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ attack_type: '', outcome: '', strength: '' });
  const [selectedRun, setSelectedRun] = useState(null);
  const [detail, setDetail] = useState(null);

  const loadRuns = () => {
    setLoading(true);
    const activeFilters = Object.fromEntries(Object.entries(filters).filter(([_, v]) => v !== ''));
    fetchRuns(activeFilters)
      .then(res => { setRuns(res.runs || []); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => { loadRuns(); }, [filters]);

  const openDetail = (run) => {
    setSelectedRun(run);
    fetchRunEvents(run.run_id)
      .then(res => setDetail(res))
      .catch(() => setDetail({ events: [], outcome: run.injection_outcome }));
  };

  const closeDetail = () => { setSelectedRun(null); setDetail(null); };

  const selectStyle = {
    background: '#161b22', border: '1px solid #30363d', borderRadius: 8,
    padding: '8px 14px', fontSize: 13, color: '#d1d5db',
    outline: 'none', cursor: 'pointer', appearance: 'none',
    backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E\")",
    backgroundRepeat: 'no-repeat', backgroundPosition: 'right 10px center', paddingRight: 32,
  };

  return (
    <div style={{ width: '100%', minHeight: '100vh', padding: '32px 40px', boxSizing: 'border-box' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28, paddingBottom: 20, borderBottom: '1px solid #1e293b' }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 900, display: 'flex', alignItems: 'center', gap: 12, background: 'linear-gradient(90deg, #60a5fa, #a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: 4 }}>
            <History size={26} color="#60a5fa" /> Incident History
          </h1>
          <p style={{ fontSize: 14, color: '#6b7280' }}>Complete audit log of all campaign and live pipeline executions.</p>
        </div>
        <button
          onClick={exportRunsCSV}
          style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'linear-gradient(135deg, #22c55e, #16a34a)', color: '#fff', padding: '10px 20px', borderRadius: 10, fontWeight: 700, fontSize: 13, border: 'none', cursor: 'pointer', boxShadow: '0 4px 15px rgba(34,197,94,0.3)', transition: 'all 0.2s' }}
          onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
          onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
        >
          <Download size={16} /> Export CSV
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, padding: '14px 20px', background: '#0d1117', border: '1px solid #1e293b', borderRadius: 12, alignItems: 'center', marginBottom: 24 }}>
        <Filter size={16} color="#60a5fa" />
        <span style={{ fontSize: 12, fontWeight: 700, color: '#60a5fa', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Filters</span>
        <div style={{ width: 1, height: 24, background: '#1e293b', margin: '0 4px' }}></div>
        <select name="attack_type" value={filters.attack_type} onChange={e => setFilters({...filters, attack_type: e.target.value})} style={selectStyle}>
          <option value="">All Attack Types</option>
          <option value="direct_injection">Direct Injection</option>
          <option value="indirect_injection">Indirect Injection</option>
          <option value="memory_poisoning">Memory Poisoning</option>
          <option value="tool_misuse">Tool Misuse</option>
        </select>
        <select name="outcome" value={filters.outcome} onChange={e => setFilters({...filters, outcome: e.target.value})} style={selectStyle}>
          <option value="">All Outcomes</option>
          <option value="full_success">Full Success</option>
          <option value="partial">Partial</option>
          <option value="ignored">Ignored</option>
          <option value="clean">Clean</option>
        </select>
        <select name="strength" value={filters.strength} onChange={e => setFilters({...filters, strength: e.target.value})} style={selectStyle}>
          <option value="">All Strengths</option>
          <option value="subtle">Subtle</option>
          <option value="moderate">Moderate</option>
          <option value="blatant">Blatant</option>
        </select>
        <div style={{ flex: 1 }}></div>
        <span style={{ fontSize: 12, color: '#475569', fontWeight: 600 }}>{runs.length} records</span>
      </div>

      {/* Table */}
      <div style={{ background: '#0d1117', border: '1px solid #1e293b', borderRadius: 14, overflow: 'hidden', boxShadow: '0 4px 24px rgba(0,0,0,0.2)' }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#6b7280', fontSize: 14 }}>Loading records...</div>
        ) : runs.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#6b7280', fontSize: 14 }}>No runs match your filters.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 900 }}>
              <thead>
                <tr style={{ background: '#161b22' }}>
                  {['Run ID', 'Scenario', 'Attack Vector', 'Strength', 'Outcome', 'Timestamp'].map((h, i) => (
                    <th key={h} style={{ padding: '14px 20px', fontSize: 10, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#60a5fa', borderBottom: '1px solid #1e293b', textAlign: i === 5 ? 'right' : 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map(run => (
                  <tr
                    key={run.run_id}
                    onClick={() => openDetail(run)}
                    style={{ borderBottom: '1px solid rgba(30,41,59,0.3)', transition: 'background 0.15s', cursor: 'pointer' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(59,130,246,0.04)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '12px 20px', fontFamily: 'monospace', fontSize: 11, color: '#8b949e' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: oc(run.injection_outcome), boxShadow: `0 0 6px ${oc(run.injection_outcome)}` }}></span>
                        {(run.run_id || '').substring(0, 12)}…
                      </span>
                    </td>
                    <td style={{ padding: '12px 20px', fontSize: 12, color: '#6b7280' }}>{run.scenario_id || '—'}</td>
                    <td style={{ padding: '12px 20px', fontSize: 12, color: '#d1d5db', fontWeight: 600, textTransform: 'capitalize' }}>{(run.injection_type || 'None').replace(/_/g, ' ')}</td>
                    <td style={{ padding: '12px 20px' }}>
                      <span style={{ padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 800, textTransform: 'uppercase', color: sc(run.attack_strength), background: `${sc(run.attack_strength)}15`, border: `1px solid ${sc(run.attack_strength)}30` }}>
                        {run.attack_strength || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '12px 20px' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 800, textTransform: 'uppercase', color: oc(run.injection_outcome), background: `${oc(run.injection_outcome)}12` }}>
                        <span style={{ width: 5, height: 5, borderRadius: '50%', background: oc(run.injection_outcome) }}></span>
                        {(run.injection_outcome || 'clean').replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td style={{ padding: '12px 20px', textAlign: 'right', fontFamily: 'monospace', fontSize: 11, color: '#6b7280' }}>
                      {new Date(run.run_started_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Detail Modal ── */}
      {selectedRun && (
        <div onClick={closeDetail} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={e => e.stopPropagation()} style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: 16, padding: 32, width: '90%', maxWidth: 720, maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 24px 80px rgba(0,0,0,0.6)' }}>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <h2 style={{ fontSize: 20, fontWeight: 900, background: 'linear-gradient(90deg, #60a5fa, #c084fc)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Incident Analysis</h2>
              <button onClick={closeDetail} style={{ background: '#1e293b', border: 'none', color: '#8b949e', width: 34, height: 34, borderRadius: 8, cursor: 'pointer', fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><X size={16} /></button>
            </div>

            {/* Run metadata */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 20 }}>
              {[
                ['Run ID', (selectedRun.run_id || '').substring(0, 16)],
                ['Attack Type', (selectedRun.injection_type || 'clean').replace(/_/g, ' ')],
                ['Strength', selectedRun.attack_strength || '—'],
                ['Outcome', (selectedRun.injection_outcome || 'clean').replace(/_/g, ' ')],
                ['Scenario', selectedRun.scenario_id || '—'],
                ['Timestamp', new Date(selectedRun.run_started_at).toLocaleString()],
              ].map(([label, val]) => (
                <div key={label} style={{ background: '#161b22', borderRadius: 8, padding: '10px 14px', border: '1px solid #1e293b' }}>
                  <div style={{ fontSize: 9, color: '#60a5fa', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>{label}</div>
                  <div style={{ fontSize: 13, color: '#d1d5db', fontWeight: 600, textTransform: 'capitalize' }}>{val}</div>
                </div>
              ))}
            </div>

            {/* Events */}
            {!detail ? (
              <div style={{ padding: 30, textAlign: 'center', color: '#6b7280' }}>Loading event data...</div>
            ) : (
              <>
                <div style={{ fontSize: 10, color: '#34d399', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 10 }}>Agent Hop Trace ({detail.events?.length || 0} events)</div>
                {(detail.events || []).map((ev, i) => (
                  <div key={i} style={{ background: '#161b22', borderRadius: 10, padding: 14, border: `1px solid ${ev.injection_present_this_event ? '#f8717130' : '#1e293b'}`, marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 800, color: ev.injection_present_this_event ? '#f87171' : '#34d399', textTransform: 'capitalize' }}>
                        Hop {ev.hop_index ?? i} — {ev.agent_role}
                      </span>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {ev.defense_triggered ? <span style={{ fontSize: 9, padding: '2px 8px', borderRadius: 4, background: '#fbbf2420', color: '#fbbf24', fontWeight: 700 }}>DEFENSE FIRED</span> : null}
                        {ev.tool_called ? <span style={{ fontSize: 9, padding: '2px 8px', borderRadius: 4, background: '#c084fc20', color: '#c084fc', fontWeight: 700 }}>🔧 {ev.tool_called}</span> : null}
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, fontSize: 11, marginBottom: 8 }}>
                      <div><span style={{ color: '#6b7280' }}>Latency:</span> <span style={{ color: '#d1d5db' }}>{ev.latency_ms ? `${ev.latency_ms}ms` : '—'}</span></div>
                      <div><span style={{ color: '#6b7280' }}>Tokens:</span> <span style={{ color: '#d1d5db' }}>{ev.input_tokens || 0}→{ev.output_tokens || 0}</span></div>
                      <div><span style={{ color: '#6b7280' }}>Confidence:</span> <span style={{ color: '#d1d5db' }}>{ev.defense_confidence_score != null ? `${(ev.defense_confidence_score * 100).toFixed(0)}%` : '—'}</span></div>
                    </div>
                    {ev.input_prompt_text && (
                      <div style={{ marginBottom: 6 }}>
                        <div style={{ fontSize: 9, color: '#fbbf24', fontWeight: 700, textTransform: 'uppercase', marginBottom: 3 }}>Input Prompt</div>
                        <div style={{ background: '#0d1117', borderRadius: 6, padding: 8, fontFamily: 'monospace', fontSize: 11, color: '#93c5fd', lineHeight: 1.5, maxHeight: 60, overflow: 'hidden', wordBreak: 'break-word' }}>
                          {ev.input_prompt_text.substring(0, 200)}{ev.input_prompt_text.length > 200 ? '…' : ''}
                        </div>
                      </div>
                    )}
                    {ev.output_text && (
                      <div>
                        <div style={{ fontSize: 9, color: '#34d399', fontWeight: 700, textTransform: 'uppercase', marginBottom: 3 }}>Agent Output</div>
                        <div style={{ background: '#0d1117', borderRadius: 6, padding: 8, fontFamily: 'monospace', fontSize: 11, color: '#8b949e', lineHeight: 1.5, maxHeight: 60, overflow: 'hidden' }}>
                          {ev.output_text.substring(0, 200)}{ev.output_text.length > 200 ? '…' : ''}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
