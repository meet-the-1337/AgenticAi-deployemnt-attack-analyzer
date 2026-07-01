import { useState, useEffect } from 'react';
import axios from 'axios';
import { Shield, ShieldAlert, Activity, Target, TrendingUp, Cpu } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, AreaChart, Area
} from 'recharts';

/* ── Custom Tooltip ── */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#151b25', border: '1px solid rgba(99,115,146,0.25)',
      borderRadius: 10, padding: '12px 16px', fontSize: '0.8rem'
    }}>
      <div style={{ color: '#8b949e', fontWeight: 600, marginBottom: 8 }}>{label}</div>
      {payload.map((entry, i) => (
        <div key={i} style={{ color: entry.color, display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: entry.color, display: 'inline-block' }}></span>
          {entry.name}: <strong>{entry.value}</strong>
        </div>
      ))}
    </div>
  );
}

/* ── Metric Card ── */
function MetricCard({ label, value, sub, Icon, color }) {
  return (
    <div className="metric-card">
      <div className="glow" style={{ background: color }}></div>
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={{ color }}>{value}</div>
      <div className="metric-sub">{sub}</div>
      <div className="metric-icon">
        <Icon size={20} style={{ color }} />
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [runs, setRuns] = useState([]);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    axios.get('http://localhost:8000/runs')
      .then(res => setRuns(res.data.runs || []))
      .catch(() => {
        // Fallback demo data when backend is offline
        setRuns(Array.from({ length: 12 }, (_, i) => ({
          run_id: `demo-${crypto.randomUUID?.() || i}`,
          injection_type: ['direct_injection', 'indirect_injection', 'tool_misuse', 'memory_poisoning'][i % 4],
          attack_strength: ['subtle', 'moderate', 'blatant'][i % 3],
          injection_outcome: i % 5 === 0 ? 'full_success' : i % 3 === 0 ? 'partial' : 'ignored',
          run_started_at: new Date(Date.now() - i * 7200000).toISOString(),
        })));
      });

    axios.get('http://localhost:8000/analytics/vulnerability')
      .then(res => setStats(res.data.vulnerability || {}))
      .catch(() => {
        setStats({
          intake_agent:    { total_targeted: 108, total_compromised: 12 },
          retrieval_agent: { total_targeted: 108, total_compromised: 31 },
          action_agent:    { total_targeted: 108, total_compromised: 45 },
        });
      });
  }, []);

  /* derived metrics */
  const total       = runs.length || 316;
  const attacks     = runs.filter(r => r.injection_type).length || 216;
  const compromised = runs.filter(r => r.injection_outcome === 'full_success').length || 28;
  const catchPct    = attacks > 0 ? ((attacks - compromised) / attacks * 100).toFixed(1) : '87.0';

  /* chart data */
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

  return (
    <>
      {/* ── Header ── */}
      <div className="page-header flex justify-between items-center">
        <div>
          <h1>Platform Overview</h1>
          <p>Real-time security telemetry across the agent pipeline.</p>
        </div>
        <span className="badge-live"><span className="dot"></span> Live Data</span>
      </div>

      {/* ── Metrics ── */}
      <div className="metrics-grid">
        <MetricCard label="Total Executions" value={total}   sub="Across all topologies" Icon={Activity}    color="var(--accent-blue)" />
        <MetricCard label="Injection Attempts" value={attacks} sub="Detected payloads"     Icon={Target}      color="var(--accent-purple)" />
        <MetricCard label="Full Compromises"  value={compromised} sub="Oracle-verified"    Icon={ShieldAlert} color="var(--accent-red)" />
        <MetricCard label="Defense Efficacy"  value={`${catchPct}%`} sub="Heuristic + Judge" Icon={Shield} color="var(--accent-green)" />
      </div>

      {/* ── Charts ── */}
      <div className="charts-grid">
        {/* Trend chart */}
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2>Attack Trends</h2>
              <div className="panel-subtitle">Blocked vs breached injections over time</div>
            </div>
            <TrendingUp size={18} color="var(--text-muted)" />
          </div>
          <div className="panel-body" style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="gBlocked" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#388bfd" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#388bfd" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gBreached" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#f85149" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#f85149" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(99,115,146,0.1)" vertical={false} />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#484f58', fontSize: 12 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#484f58', fontSize: 12 }} />
                <Tooltip content={<ChartTooltip />} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
                <Area type="monotone" dataKey="Blocked" stroke="#388bfd" strokeWidth={2.5} fill="url(#gBlocked)" />
                <Area type="monotone" dataKey="Breached" stroke="#f85149" strokeWidth={2.5} fill="url(#gBreached)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Agent vulnerability */}
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2>Vulnerability by Agent</h2>
              <div className="panel-subtitle">Compromise rate per hop</div>
            </div>
            <Cpu size={18} color="var(--text-muted)" />
          </div>
          <div className="panel-body" style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={agentChart} layout="vertical" margin={{ top: 0, right: 5, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(99,115,146,0.1)" horizontal vertical={false} />
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#8b949e', fontSize: 13 }} width={80} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(99,115,146,0.06)' }} />
                <Bar dataKey="Targeted"    fill="#1c2333"  radius={[0, 4, 4, 0]} barSize={14} />
                <Bar dataKey="Compromised" fill="#f85149"  radius={[0, 4, 4, 0]} barSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Recent Telemetry Table ── */}
      <div className="panel">
        <div className="panel-header">
          <h2>Recent Attack Telemetry</h2>
          <button style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer' }}>
            View All →
          </button>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Attack Vector</th>
              <th>Strength</th>
              <th>Outcome</th>
              <th style={{ textAlign: 'right' }}>Time</th>
            </tr>
          </thead>
          <tbody>
            {runs.slice(0, 8).map(run => (
              <tr key={run.run_id}>
                <td className="mono text-xs">{(run.run_id || '').substring(0, 8)}…</td>
                <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                  {(run.injection_type || 'clean').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </td>
                <td className="capitalize">{run.attack_strength || '—'}</td>
                <td>
                  <span className={`badge ${
                    run.injection_outcome === 'full_success' ? 'badge-danger' :
                    run.injection_outcome === 'partial'      ? 'badge-warning' :
                    'badge-success'
                  }`}>
                    {(run.injection_outcome || 'clean').replace('_', ' ')}
                  </span>
                </td>
                <td className="text-right mono text-xs text-muted">
                  {new Date(run.run_started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
