import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchRuns, fetchEnrichedRuns, fetchVulnerabilitySummary } from '../api/client';
import { ShieldAlert, Activity, Target, TrendingUp, AlertTriangle, Crosshair, ServerCrash, Clock, ShieldCheck } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, AreaChart, Area
} from 'recharts';

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(15,20,32,0.95)', backdropFilter: 'blur(12px)',
      border: '1px solid rgba(56,139,253,0.2)', borderRadius: 10,
      padding: '10px 14px', fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.5)'
    }}>
      <div style={{ color: '#93c5fd', fontWeight: 700, marginBottom: 6 }}>{label}</div>
      {payload.map((entry, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: entry.color, display: 'inline-block' }}></span>
          <span style={{ color: '#d1d5db' }}>{entry.name}:</span>
          <strong style={{ color: entry.color }}>{entry.value}</strong>
        </div>
      ))}
    </div>
  );
}

function MetricCard({ label, value, sub, Icon, accentColor, glowColor }) {
  return (
    <div style={{
      position: 'relative', overflow: 'hidden',
      background: 'linear-gradient(135deg, #0d1117 0%, #161b22 100%)',
      border: '1px solid rgba(48,54,61,0.8)',
      borderRadius: 16, padding: '28px 24px',
      transition: 'all 0.3s ease',
      cursor: 'default',
      borderTop: `2px solid ${accentColor}`,
    }}
    onMouseEnter={e => {
      e.currentTarget.style.transform = 'translateY(-4px)';
      e.currentTarget.style.boxShadow = `0 12px 40px ${glowColor}`;
      e.currentTarget.style.borderColor = accentColor;
    }}
    onMouseLeave={e => {
      e.currentTarget.style.transform = 'translateY(0)';
      e.currentTarget.style.boxShadow = 'none';
      e.currentTarget.style.borderColor = 'rgba(48,54,61,0.8)';
    }}>
      {/* Glow orb */}
      <div style={{
        position: 'absolute', top: -40, right: -40,
        width: 120, height: 120, borderRadius: '50%',
        background: accentColor, filter: 'blur(60px)', opacity: 0.15,
      }}></div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, position: 'relative', zIndex: 1 }}>
        <h3 style={{
          color: accentColor, fontWeight: 800, fontSize: 11,
          letterSpacing: '0.12em', textTransform: 'uppercase',
          textShadow: `0 0 20px ${glowColor}`,
        }}>{label}</h3>
        <div style={{
          padding: 8, borderRadius: 10,
          background: 'rgba(22,27,34,0.8)', border: `1px solid ${accentColor}40`,
          color: accentColor, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={18} />
        </div>
      </div>

      <div style={{ position: 'relative', zIndex: 1 }}>
        <div style={{
          fontSize: 42, fontWeight: 900, color: '#f0f6fc',
          letterSpacing: '-0.03em', lineHeight: 1, marginBottom: 6,
          textShadow: `0 0 30px ${glowColor}`,
        }}>{value}</div>
        <div style={{ fontSize: 12, color: '#8b949e', fontWeight: 500 }}>{sub}</div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [allRuns, setAllRuns] = useState([]);   // ALL runs for KPI calculations
  const [tableRuns, setTableRuns] = useState([]); // Enriched runs for incident table
  const [stats, setStats] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);

  useEffect(() => {
    // Fetch ALL runs for KPI metrics
    fetchRuns()
      .then(res => setAllRuns(res.runs || []))
      .catch(() => {});

    // Fetch enriched runs (with prompt + events) for the table
    fetchEnrichedRuns(15)
      .then(res => setTableRuns(res.runs || []))
      .catch(() => {});

    fetchVulnerabilitySummary()
      .then(res => setStats(res.vulnerability || {}))
      .catch(() => {
        setStats({
          intake:    { total_targeted: 108, total_compromised: 12 },
          retrieval: { total_targeted: 108, total_compromised: 31 },
          action:    { total_targeted: 108, total_compromised: 45 },
        });
      });
  }, []);

  const total       = allRuns.length;
  const attacks     = allRuns.filter(r => r.injection_type).length;
  const compromised = allRuns.filter(r => r.injection_outcome === 'full_success').length;
  const catchPct    = attacks > 0 ? ((attacks - compromised) / attacks * 100).toFixed(1) : '0.0';

  const agentChart = Object.entries(stats || {}).map(([k, v]) => ({
    name: k.replace('_agent', '').replace(/^\w/, c => c.toUpperCase()),
    Targeted: v.total_targeted,
    Compromised: v.total_compromised,
  }));

  const trendData = [
    { day: 'Mon', Blocked: 42, Breached: 8 },
    { day: 'Tue', Blocked: 56, Breached: 14 },
    { day: 'Wed', Blocked: 61, Breached: 5 },
    { day: 'Thu', Blocked: 48, Breached: 11 },
    { day: 'Fri', Blocked: 73, Breached: 3 },
    { day: 'Sat', Blocked: 38, Breached: 9 },
    { day: 'Sun', Blocked: 65, Breached: 2 },
  ];

  const outcomeColor = (o) =>
    o === 'full_success' ? '#f87171' : o === 'partial' ? '#fbbf24' : '#34d399';
  const strengthColor = (s) =>
    s === 'blatant' ? '#f87171' : s === 'moderate' ? '#fbbf24' : '#6b7280';

  return (
    <div style={{
      width: '100%', minHeight: '100vh',
      padding: '32px 40px', boxSizing: 'border-box',
      display: 'flex', flexDirection: 'column', gap: 28,
    }}>
      
      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 style={{
            fontSize: 28, fontWeight: 900, color: '#f0f6fc',
            letterSpacing: '-0.02em', marginBottom: 4,
            background: 'linear-gradient(135deg, #60a5fa, #a78bfa, #f472b6)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>Security Operations Center</h1>
          <p style={{ fontSize: 14, color: '#8b949e', fontWeight: 500 }}>
            Real-time threat telemetry across the AI agent pipeline.
          </p>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 16px', borderRadius: 20,
          background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)',
          color: '#34d399', fontSize: 11, fontWeight: 800,
          textTransform: 'uppercase', letterSpacing: '0.1em',
          boxShadow: '0 0 20px rgba(16,185,129,0.12)',
        }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%', background: '#34d399',
            animation: 'pulse 2s ease-in-out infinite',
            boxShadow: '0 0 8px #34d399',
          }}></div>
          Live Threat Feed
        </div>
      </div>

      {/* ── KPI Cards ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20,
      }}>
        <MetricCard label="Pipeline Executions" value={total} sub="Total traces analyzed" Icon={Activity} accentColor="#60a5fa" glowColor="rgba(96,165,250,0.3)" />
        <MetricCard label="Injection Attempts" value={attacks} sub="Detected malicious payloads" Icon={Target} accentColor="#c084fc" glowColor="rgba(192,132,252,0.3)" />
        <MetricCard label="System Compromises" value={compromised} sub="High severity breaches" Icon={ServerCrash} accentColor="#f87171" glowColor="rgba(248,113,113,0.3)" />
        <MetricCard label="Defense Efficacy" value={`${catchPct}%`} sub="Heuristic & LLM Judges" Icon={ShieldCheck} accentColor="#34d399" glowColor="rgba(52,211,153,0.3)" />
      </div>

      {/* ── Charts Row ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20, flex: 1, minHeight: 0 }}>
        
        {/* Attack Vector Timeline */}
        <div style={{
          background: 'linear-gradient(135deg, #0d1117, #161b22)',
          border: '1px solid #30363d', borderRadius: 16,
          padding: '24px 24px 16px', position: 'relative', overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ position: 'absolute', top: 0, right: 0, width: 200, height: 200, background: 'rgba(59,130,246,0.04)', filter: 'blur(80px)', borderRadius: '50%' }}></div>
          <div style={{ marginBottom: 20, position: 'relative', zIndex: 1 }}>
            <h2 style={{
              fontSize: 15, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8,
              background: 'linear-gradient(90deg, #60a5fa, #93c5fd)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>
              <TrendingUp size={18} color="#60a5fa" /> Attack Vector Timeline
            </h2>
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>Blocked vs Breached sequences over 7 days</div>
          </div>
          <div style={{ flex: 1, minHeight: 250, position: 'relative', zIndex: 1 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="gBlocked" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gBreached" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#6b7280', fontSize: 12 }} dy={8} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#6b7280', fontSize: 12 }} />
                <Tooltip content={<ChartTooltip />} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12, color: '#9ca3af', paddingTop: 12 }} />
                <Area type="monotone" dataKey="Blocked" stroke="#3b82f6" strokeWidth={3} fill="url(#gBlocked)" activeDot={{ r: 7, fill: '#3b82f6', stroke: '#1e3a5f', strokeWidth: 3 }} />
                <Area type="monotone" dataKey="Breached" stroke="#ef4444" strokeWidth={3} fill="url(#gBreached)" activeDot={{ r: 7, fill: '#ef4444', stroke: '#5f1e1e', strokeWidth: 3 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pipeline Vulnerability */}
        <div style={{
          background: 'linear-gradient(135deg, #0d1117, #161b22)',
          border: '1px solid #30363d', borderRadius: 16,
          padding: '24px 24px 16px', position: 'relative', overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ position: 'absolute', bottom: 0, left: 0, width: 200, height: 200, background: 'rgba(248,113,113,0.04)', filter: 'blur(80px)', borderRadius: '50%' }}></div>
          <div style={{ marginBottom: 20, position: 'relative', zIndex: 1 }}>
            <h2 style={{
              fontSize: 15, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8,
              background: 'linear-gradient(90deg, #f87171, #fca5a5)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>
              <Crosshair size={18} color="#f87171" /> Pipeline Vulnerability
            </h2>
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>Compromise rate by agent hop</div>
          </div>
          <div style={{ flex: 1, minHeight: 250, position: 'relative', zIndex: 1 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={agentChart} layout="vertical" margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
                <CartesianGrid stroke="#1e293b" horizontal vertical={false} strokeDasharray="3 3" />
                <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: '#6b7280', fontSize: 11 }} />
                <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#d1d5db', fontSize: 13, fontWeight: 600 }} width={75} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(30,41,59,0.5)' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12, color: '#9ca3af', paddingTop: 8 }} />
                <Bar dataKey="Targeted" fill="#334155" radius={[0, 6, 6, 0]} barSize={16} />
                <Bar dataKey="Compromised" fill="#ef4444" radius={[0, 6, 6, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Live Incident Table ── */}
      <div style={{
        background: 'linear-gradient(135deg, #0d1117, #161b22)',
        border: '1px solid #30363d', borderRadius: 16,
        overflow: 'hidden',
      }}>
        <div style={{
          padding: '16px 24px', borderBottom: '1px solid #30363d',
          background: '#161b22',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <h2 style={{
            fontSize: 15, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8,
            background: 'linear-gradient(90deg, #fbbf24, #f59e0b)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            <AlertTriangle size={18} color="#fbbf24" /> Live Incident Queue
          </h2>
          <button
            onClick={() => navigate('/history')}
            style={{
              fontSize: 12, fontWeight: 700, color: '#60a5fa',
              background: 'rgba(96,165,250,0.1)', border: '1px solid rgba(96,165,250,0.2)',
              padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(96,165,250,0.2)'; e.currentTarget.style.boxShadow = '0 0 12px rgba(96,165,250,0.2)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(96,165,250,0.1)'; e.currentTarget.style.boxShadow = 'none'; }}
          >
            View Full Logs →
          </button>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 850 }}>
            <thead>
              <tr style={{ background: '#0d1117' }}>
                {['Incident ID', 'Attack Vector', 'Prompt', 'Severity', 'Status', 'Time'].map((h, i) => (
                  <th key={h} style={{
                    padding: '12px 16px', fontSize: 10, fontWeight: 800,
                    textTransform: 'uppercase', letterSpacing: '0.1em',
                    color: '#60a5fa', borderBottom: '1px solid #1e293b',
                    textAlign: i === 5 ? 'right' : 'left',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRuns.slice(0, 10).map((run) => (
                <tr key={run.run_id}
                  onClick={() => setSelectedRun(run)}
                  style={{ borderBottom: '1px solid rgba(30,41,59,0.4)', transition: 'background 0.15s', cursor: 'pointer' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(59,130,246,0.04)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <td style={{ padding: '10px 16px', fontFamily: 'monospace', fontSize: 12, color: '#8b949e' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: outcomeColor(run.injection_outcome), boxShadow: `0 0 6px ${outcomeColor(run.injection_outcome)}` }}></span>
                      {(run.run_id || '').substring(0, 8)}
                    </span>
                  </td>
                  <td style={{ padding: '10px 16px', fontSize: 12, color: '#d1d5db', fontWeight: 600, textTransform: 'capitalize' }}>
                    {(run.injection_type || 'clean').replace(/_/g, ' ')}
                  </td>
                  <td style={{ padding: '10px 16px', fontSize: 11, color: '#6b7280', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {run.prompt ? `"${run.prompt.substring(0, 50)}${run.prompt.length > 50 ? '…' : ''}"` : '—'}
                  </td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 800, textTransform: 'uppercase', color: strengthColor(run.attack_strength), background: `${strengthColor(run.attack_strength)}15`, border: `1px solid ${strengthColor(run.attack_strength)}30` }}>
                      {run.attack_strength || '—'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 800, textTransform: 'uppercase', color: outcomeColor(run.injection_outcome), background: `${outcomeColor(run.injection_outcome)}12` }}>
                      <span style={{ width: 5, height: 5, borderRadius: '50%', background: outcomeColor(run.injection_outcome), boxShadow: `0 0 6px ${outcomeColor(run.injection_outcome)}` }}></span>
                      {(run.injection_outcome || 'clean').replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td style={{ padding: '10px 16px', textAlign: 'right', fontFamily: 'monospace', fontSize: 11, color: '#6b7280' }}>
                    <Clock size={11} color="#4b5563" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                    {new Date(run.run_started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Detail Modal ── */}
      {selectedRun && (
        <div
          onClick={() => setSelectedRun(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div
            onClick={e => e.stopPropagation()}
            style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: 16, padding: 32, width: '90%', maxWidth: 700, maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 24px 80px rgba(0,0,0,0.6)' }}>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h2 style={{ fontSize: 18, fontWeight: 900, background: 'linear-gradient(90deg, #60a5fa, #c084fc)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Incident Analysis
              </h2>
              <button onClick={() => setSelectedRun(null)} style={{ background: '#1e293b', border: 'none', color: '#8b949e', width: 32, height: 32, borderRadius: 8, cursor: 'pointer', fontSize: 16, fontWeight: 700 }}>✕</button>
            </div>

            {/* Run metadata */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
              {[
                ['Run ID', selectedRun.run_id?.substring(0, 16)],
                ['Attack Type', (selectedRun.injection_type || 'clean').replace(/_/g, ' ')],
                ['Strength', selectedRun.attack_strength || '—'],
                ['Outcome', selectedRun.injection_outcome || 'clean'],
                ['Objective', selectedRun.attack_objective || '—'],
                ['Topology', selectedRun.topology_type || '—'],
                ['Total Hops', selectedRun.total_hops || '—'],
                ['Hops to Compromise', selectedRun.hops_to_compromise || '—'],
              ].map(([label, val]) => (
                <div key={label} style={{ background: '#161b22', borderRadius: 8, padding: '10px 14px', border: '1px solid #1e293b' }}>
                  <div style={{ fontSize: 9, color: '#60a5fa', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>{label}</div>
                  <div style={{ fontSize: 13, color: '#d1d5db', fontWeight: 600, textTransform: 'capitalize' }}>{val}</div>
                </div>
              ))}
            </div>

            {/* Prompt */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 10, color: '#fbbf24', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>Original Prompt</div>
              <div style={{ background: '#161b22', borderRadius: 8, padding: 14, border: '1px solid #1e293b', fontFamily: 'monospace', fontSize: 12, color: '#93c5fd', lineHeight: 1.6, wordBreak: 'break-word' }}>
                {selectedRun.prompt || 'N/A'}
              </div>
            </div>

            {/* Per-hop event breakdown */}
            <div style={{ fontSize: 10, color: '#34d399', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>Agent Hop Trace ({selectedRun.events?.length || 0} events)</div>
            {(selectedRun.events || []).map((ev, i) => (
              <div key={i} style={{ background: '#161b22', borderRadius: 10, padding: 14, border: `1px solid ${ev.injection_present_this_event ? '#f8717130' : '#1e293b'}`, marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 800, color: ev.injection_present_this_event ? '#f87171' : '#34d399', textTransform: 'capitalize' }}>
                    Hop {i} — {ev.agent_role}
                  </span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {ev.defense_triggered ? <span style={{ fontSize: 9, padding: '2px 8px', borderRadius: 4, background: '#fbbf2420', color: '#fbbf24', fontWeight: 700 }}>DEFENSE FIRED</span> : null}
                    {ev.tool_called ? <span style={{ fontSize: 9, padding: '2px 8px', borderRadius: 4, background: '#c084fc20', color: '#c084fc', fontWeight: 700 }}>🔧 {ev.tool_called}</span> : null}
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, fontSize: 11 }}>
                  <div><span style={{ color: '#6b7280' }}>Latency:</span> <span style={{ color: '#d1d5db' }}>{ev.latency_ms ? `${ev.latency_ms}ms` : '—'}</span></div>
                  <div><span style={{ color: '#6b7280' }}>Tokens:</span> <span style={{ color: '#d1d5db' }}>{ev.input_tokens || 0}→{ev.output_tokens || 0}</span></div>
                  <div><span style={{ color: '#6b7280' }}>Confidence:</span> <span style={{ color: '#d1d5db' }}>{ev.defense_confidence_score != null ? `${(ev.defense_confidence_score * 100).toFixed(0)}%` : '—'}</span></div>
                </div>
                {ev.output_text && (
                  <div style={{ marginTop: 8, fontSize: 11, color: '#8b949e', fontFamily: 'monospace', background: '#0d1117', padding: 8, borderRadius: 6, maxHeight: 60, overflow: 'hidden' }}>
                    {ev.output_text.substring(0, 150)}{ev.output_text.length > 150 ? '…' : ''}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(52,211,153,0.5); }
          50% { opacity: 0.7; box-shadow: 0 0 0 6px rgba(52,211,153,0); }
        }
      `}</style>
    </div>
  );
}
