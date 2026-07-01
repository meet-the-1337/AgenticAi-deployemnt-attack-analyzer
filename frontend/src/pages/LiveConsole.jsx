import { useState } from 'react';
import axios from 'axios';
import ReactFlow, { Background, Controls, MarkerType } from 'reactflow';
import 'reactflow/dist/style.css';
import { Play, Terminal, AlertTriangle, ShieldCheck } from 'lucide-react';

const NODES_BASE = [
  { id: 'intake',    position: { x: 50,  y: 140 }, data: { label: 'Intake Agent' } },
  { id: 'retrieval', position: { x: 300, y: 140 }, data: { label: 'Retrieval Agent' } },
  { id: 'action',    position: { x: 550, y: 140 }, data: { label: 'Action Agent' } },
  { id: 'memory',    position: { x: 300, y: 320 }, data: { label: 'Session Memory' } },
];

const EDGES = [
  { id: 'e1', source: 'intake', target: 'retrieval', animated: true, markerEnd: { type: MarkerType.ArrowClosed, color: '#484f58' }, style: { stroke: '#484f58', strokeWidth: 2 } },
  { id: 'e2', source: 'retrieval', target: 'action', animated: true, markerEnd: { type: MarkerType.ArrowClosed, color: '#484f58' }, style: { stroke: '#484f58', strokeWidth: 2 } },
  { id: 'e3', source: 'retrieval', target: 'memory', animated: true, style: { stroke: '#388bfd', strokeWidth: 1.5, strokeDasharray: '6 4' } },
  { id: 'e4', source: 'action', target: 'memory', animated: true, style: { stroke: '#388bfd', strokeWidth: 1.5, strokeDasharray: '6 4' } },
];

function styleNode(node, event, outcome) {
  const base = { fontFamily: "'Inter', sans-serif", fontWeight: 600, fontSize: '0.8rem', borderRadius: 12, padding: '10px 18px', transition: 'all 0.5s cubic-bezier(0.16,1,0.3,1)' };
  if (!event) return { ...node, style: { ...base, background: '#1c2333', borderColor: '#2d3548', borderWidth: 1.5, color: '#e6edf3' } };

  if (event.defense_triggered) {
    return { ...node, style: { ...base, background: 'rgba(210,153,34,0.08)', borderColor: '#d29922', borderWidth: 2, color: '#f0c040', boxShadow: '0 0 18px rgba(210,153,34,0.15)' } };
  }
  if (event.injection_present_this_event && outcome === 'full_success') {
    return { ...node, style: { ...base, background: 'rgba(248,81,73,0.08)', borderColor: '#f85149', borderWidth: 2, color: '#fca5a5', boxShadow: '0 0 18px rgba(248,81,73,0.2)' } };
  }
  return { ...node, style: { ...base, background: 'rgba(63,185,80,0.06)', borderColor: '#3fb950', borderWidth: 1.5, color: '#7ee787' } };
}

export default function LiveConsole() {
  const [prompt, setPrompt] = useState('I need help with my account CUST-104.');
  const [mode, setMode] = useState('benign');
  const [attackType, setAttackType] = useState('direct_prompt_injection');
  const [nodes, setNodes] = useState(NODES_BASE);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const colorNodes = (events, outcome) => {
    setNodes(NODES_BASE.map(n => {
      const ev = events.find(e => e.agent_role === n.id);
      return styleNode(n, ev, outcome);
    }));
  };

  const handleRun = async () => {
    setLoading(true);
    setResult(null);
    setNodes(NODES_BASE);

    try {
      const res = await axios.post('http://localhost:8000/run/live', {
        prompt,
        mode,
        attack_type: mode === 'attack' ? attackType : undefined,
        strength: 'blatant',
      });
      setResult(res.data);
      colorNodes(res.data.events, res.data.outcome);
    } catch {
      // offline demo
      setTimeout(() => {
        const mock = mode === 'attack'
          ? { outcome: 'full_success', run_id: 'demo-' + Date.now(), events: [
              { agent_role: 'intake', injection_present_this_event: 1, defense_triggered: 0 },
              { agent_role: 'retrieval', injection_present_this_event: 1, defense_triggered: 1 },
              { agent_role: 'action', injection_present_this_event: 1, defense_triggered: 0 },
            ]}
          : { outcome: 'clean', run_id: 'demo-' + Date.now(), events: [
              { agent_role: 'intake', injection_present_this_event: 0, defense_triggered: 0 },
              { agent_role: 'retrieval', injection_present_this_event: 0, defense_triggered: 0 },
              { agent_role: 'action', injection_present_this_event: 0, defense_triggered: 0 },
            ]};
        setResult(mock);
        colorNodes(mock.events, mock.outcome);
        setLoading(false);
      }, 1200);
      return;
    }
    setLoading(false);
  };

  return (
    <>
      {/* ── Header ── */}
      <div className="page-header">
        <h1 style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Terminal size={28} color="var(--accent-blue)" /> Live Execution Console
        </h1>
        <p>Inject payloads and observe real-time graph propagation with defense telemetry.</p>
      </div>

      {/* ── Controls ── */}
      <div className="panel" style={{ marginBottom: 20 }}>
        <div className="panel-body console-controls">
          <div className="console-row">
            <div className="toggle-group">
              <button className={`toggle-btn ${mode === 'benign' ? 'active-clean' : ''}`} onClick={() => setMode('benign')}>
                Clean Traffic
              </button>
              <button className={`toggle-btn ${mode === 'attack' ? 'active-attack' : ''}`} onClick={() => setMode('attack')}>
                ⚡ Attack Payload
              </button>
            </div>

            {mode === 'attack' && (
              <select className="input" value={attackType} onChange={e => setAttackType(e.target.value)} style={{ maxWidth: 220 }}>
                <option value="direct_prompt_injection">Direct Injection</option>
                <option value="indirect_prompt_injection">Indirect Injection</option>
                <option value="memory_poisoning">Memory Poisoning</option>
                <option value="tool_misuse">Tool Misuse</option>
              </select>
            )}
          </div>

          <div className="console-input-row">
            <input
              className="input"
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder={mode === 'attack' ? 'Payload will be injected around this prompt…' : 'Enter a genuine customer query…'}
            />
            <button className="btn btn-primary" onClick={handleRun} disabled={loading} style={{ minWidth: 160 }}>
              {loading
                ? <><span className="spinner"></span> Processing…</>
                : <><Play size={16} /> Execute Trace</>
              }
            </button>
          </div>
        </div>
      </div>

      {/* ── Flow Graph ── */}
      <div className="flow-container" style={{ height: 480 }}>
        <ReactFlow nodes={nodes} edges={EDGES} fitView proOptions={{ hideAttribution: true }}>
          <Background color="#1c2333" gap={28} size={1.5} />
          <Controls />
        </ReactFlow>

        {result && (
          <div className="result-overlay">
            <h3>
              {result.outcome === 'full_success'
                ? <><AlertTriangle size={20} color="var(--accent-red)" /> Compromise Detected</>
                : <><ShieldCheck size={20} color="var(--accent-green)" /> Execution Secured</>
              }
            </h3>
            <div className="result-row">
              <span className="result-label">Run ID</span>
              <span className="result-value mono text-xs" style={{ background: 'var(--bg-elevated)', padding: '3px 8px', borderRadius: 6 }}>
                {(result.run_id || '').substring(0, 12)}
              </span>
            </div>
            <div className="result-row">
              <span className="result-label">Oracle Verdict</span>
              <span className="result-value" style={{ color: result.outcome === 'full_success' ? 'var(--accent-red)' : 'var(--accent-green)', textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.04em' }}>
                {(result.outcome || '').replace(/_/g, ' ')}
              </span>
            </div>
            <div className="result-row">
              <span className="result-label">Hops Traced</span>
              <span className="result-value">{result.events?.length || 0}</span>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
