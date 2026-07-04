import { ReactFlow, Background } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

const ROLE_TO_ID = {
  'intake': 'intake', 'intake_agent': 'intake',
  'retrieval': 'retrieval', 'retrieval_agent': 'retrieval', 
  'action': 'action', 'action_agent': 'action',
};

// Map hop_index to node id
const HOP_TO_NODE = { 0: 'intake', 1: 'retrieval', 2: 'action' };

export default function AgentFlowGraph({ events = [], outcome = '', activeHop = -1 }) {
  
  // Compute node status per node
  const nodeStatus = {
    user: 'clean',  // user is always "done"
    intake: 'pending',
    retrieval: 'pending', 
    action: 'pending',
    memory: 'pending',
  };
  
  events.forEach(e => {
    const id = ROLE_TO_ID[e.agent_role];
    if (!id) return;
    nodeStatus[id] = e.defense_triggered ? 'defended' : 'clean';
  });
  
  if (activeHop >= 0 && activeHop <= 2) {
    const activeNode = HOP_TO_NODE[activeHop];
    if (nodeStatus[activeNode] === 'pending') {
      nodeStatus[activeNode] = 'executing';
    }
  }
  
  if (outcome === 'full_success') {
    const attackEvent = events.find(e => 
      e.tool_called && 
      ['escalate_to_admin', 'send_email', 'update_ticket'].includes(e.tool_called)
    );
    const targetId = attackEvent ? ROLE_TO_ID[attackEvent.agent_role] : 'action';
    nodeStatus[targetId] = 'attacked';
    
    const hasMemoryOp = events.some(e => 
      (e.memory_ops_summary || '').includes('agent_instructions'));
    if (hasMemoryOp) {
      nodeStatus.memory = 'attacked';
    }
  } else if (outcome === 'partial') {
    // For partial compromise, highlight retrieval or action if impacted
    const hasMemoryOp = events.some(e => 
      (e.memory_ops_summary || '').includes('agent_instructions'));
    if (hasMemoryOp) {
      nodeStatus.memory = 'defended';
    }
  }
  
  // Status → visual style
  const STATUS_STYLE = {
    pending:   { background:'#1e293b', border:'2px solid #475569', color:'#94a3b8' },
    executing: { background:'#1e3a5f', border:'2px solid #3b82f6', color:'#93c5fd',
                 boxShadow:'0 0 12px rgba(59,130,246,0.5)', className: 'executing-node' },
    clean:     { background:'#064e3b', border:'2px solid #10b981', color:'#6ee7b7' },
    defended:  { background:'#78350f', border:'2px solid #f59e0b', color:'#fcd34d' },
    attacked:  { background:'#7f1d1d', border:'2px solid #ef4444', color:'#fca5a5' },
    memory_hit:{ background:'#7f1d1d', border:'2px solid #ef4444', color:'#fca5a5' },
  };
  
  // Build edge labels from actual event data
  const getEdgeLabel = (source, target) => {
    if (source === 'user' && target === 'intake') {
      return events[0]?.input_prompt_text?.substring(0, 45) + '...' || '';
    }
    if (source === 'intake' && target === 'retrieval') {
      const e = events.find(e => ROLE_TO_ID[e.agent_role] === 'intake');
      return e?.output_text?.substring(0, 45) + '...' || '';
    }
    if (source === 'retrieval' && target === 'action') {
      return 'KB results + customer context';
    }
    if (source === 'memory' && target === 'action') {
      const e = events.find(e => 
        (e.memory_ops_summary || '').includes('agent_instructions'));
      return e ? '⚠️ Poisoned instructions read' : 'Memory context';
    }
    return '';
  };
  
  // Only show edge label if source node is complete
  const isNodeComplete = (id) => 
    !['pending','executing'].includes(nodeStatus[id]);
  
  const nodes = [
    { id: 'user',      position: { x: 0,   y: 120 }, 
      data: { label: '👤 User Input' }, type: 'input' },
    { id: 'intake',    position: { x: 220, y: 120 },
      data: { label: '📥 Intake Agent' } },
    { id: 'retrieval', position: { x: 440, y: 120 },
      data: { label: '🔍 Retrieval Agent' } },
    { id: 'action',    position: { x: 660, y: 120 },
      data: { label: '⚡ Action Agent' } },
    { id: 'memory',    position: { x: 440, y: 280 },
      data: { label: '🧠 Memory Store' } },
  ].map(n => {
    const styleDef = STATUS_STYLE[nodeStatus[n.id]] || STATUS_STYLE.pending;
    const { className, ...styleProps } = styleDef;
    return { 
      ...n, 
      className: className || '',
      style: { 
        ...styleProps, 
        borderRadius: '10px', 
        padding: '10px 18px',
        fontSize: '13px',
        fontWeight: '600',
        minWidth: '140px',
        textAlign: 'center',
        transition: 'all 0.3s ease'
      }
    };
  });
  
  const edges = [
    { id:'u-i', source:'user', target:'intake', animated: isNodeComplete('user'),
      label: isNodeComplete('user') ? getEdgeLabel('user','intake') : '',
      labelStyle: { fontSize: 11, fill: '#94a3b8', fontWeight: 500 },
      labelBgStyle: { fill: '#1e293b', fillOpacity: 0.8, rx: 4, ry: 4 },
      labelBgPadding: [6, 4],
      style: { stroke: isNodeComplete('user') ? '#3b82f6' : '#475569', strokeWidth: 2 }},
    { id:'i-r', source:'intake', target:'retrieval', animated: isNodeComplete('intake'),
      label: isNodeComplete('intake') ? getEdgeLabel('intake','retrieval') : '',
      labelStyle: { fontSize: 11, fill: '#94a3b8', fontWeight: 500 },
      labelBgStyle: { fill: '#1e293b', fillOpacity: 0.8, rx: 4, ry: 4 },
      labelBgPadding: [6, 4],
      style: { stroke: isNodeComplete('intake') ? '#3b82f6' : '#475569', strokeWidth: 2 }},
    { id:'r-a', source:'retrieval', target:'action', animated: isNodeComplete('retrieval'),
      label: isNodeComplete('retrieval') ? getEdgeLabel('retrieval','action') : '',
      labelStyle: { fontSize: 11, fill: '#94a3b8', fontWeight: 500 },
      labelBgStyle: { fill: '#1e293b', fillOpacity: 0.8, rx: 4, ry: 4 },
      labelBgPadding: [6, 4],
      style: { stroke: isNodeComplete('retrieval') ? '#3b82f6' : '#475569', strokeWidth: 2 }},
    { id:'r-m', source:'retrieval', target:'memory', animated: false,
      style: { stroke: '#475569', strokeDasharray: '4', strokeWidth: 1.5 }},
    { id:'m-a', source:'memory', target:'action', animated: isNodeComplete('memory'),
      label: isNodeComplete('memory') ? getEdgeLabel('memory','action') : '',
      labelStyle: { fontSize: 11, fill: '#f87171', fontWeight: 600 },
      labelBgStyle: { fill: '#1e293b', fillOpacity: 0.8, rx: 4, ry: 4 },
      labelBgPadding: [6, 4],
      style: { stroke: nodeStatus.memory === 'attacked' ? '#ef4444' : '#475569',
               strokeDasharray: nodeStatus.memory === 'attacked' ? '0' : '4', strokeWidth: 1.5 }},
  ];
  
  return (
    <div className="bg-[#0d1117] border border-[#30363d] rounded-xl overflow-hidden shadow-lg mt-6">
      <div className="px-5 py-3 border-b border-[#30363d] bg-[#161b22] flex items-center justify-between">
        <h3 className="font-semibold text-gray-200">
          Agent Pipeline — Attack Propagation Graph
        </h3>
        <div className="flex gap-3 text-xs text-gray-500 font-medium">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-green-500"/> Clean
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-yellow-500"/> Defended
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500"/> Compromised
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]"/> Executing
          </span>
        </div>
      </div>
      
      <div style={{ height: 380 }}>
        <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}
          nodesDraggable={false} nodesConnectable={false}
          elementsSelectable={false} zoomOnScroll={false}
          panOnDrag={false}>
          <Background color="#1c2333" gap={24} size={1.5} />
        </ReactFlow>
      </div>
      
      {/* Attack path summary below graph */}
      {outcome && outcome !== '' && (
        <div className={`px-5 py-3 border-t border-[#30363d] text-sm font-medium
          ${outcome === 'full_success' 
            ? 'bg-red-950/40 text-red-300' 
            : outcome === 'partial'
            ? 'bg-yellow-950/40 text-yellow-300'
            : 'bg-green-950/40 text-green-300'}`}>
          {outcome === 'full_success' && (
            <>🔴 Attack propagated: User → 
              {events.map(e => {
                const id = ROLE_TO_ID[e.agent_role];
                const labels = {intake:'Intake',retrieval:'Retrieval',action:'Action'};
                return id ? ` ${labels[id]} →` : '';
              })}
              {' '}<strong>COMPROMISED</strong>
              {events.find(e => e.tool_called) && 
                ` via ${events.find(e => e.tool_called).tool_called}`}
            </>
          )}
          {outcome === 'partial' && 
            '🟡 Attack partially executed — influenced agent behavior but not fully successful'}
          {(outcome === 'ignored' || outcome === 'clean') && 
            '✅ Pipeline completed cleanly — no unauthorized actions taken'}
        </div>
      )}
    </div>
  );
}
