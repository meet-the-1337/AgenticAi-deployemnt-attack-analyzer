import React from 'react';

function FlowChart({ events, outcome }) {
  if (!events || events.length === 0) return null;

  // Determine node states
  const nodeStates = {
    intake: 'grey',
    retrieval: 'grey', 
    action: 'grey',
    memory: 'grey'
  };

  events.forEach(e => {
    // Mark executing nodes as completed (blue → green)
    if (e.agent_role && nodeStates[e.agent_role] === 'grey') {
      nodeStates[e.agent_role] = 'green';
    }
    // Defense triggered = yellow (overrides green, not red)
    if (e.defense_triggered) {
      nodeStates[e.agent_role] = 'yellow';
    }
  });

  // Attack succeeded: find which hop and color that node red
  if (outcome === 'full_success') {
    // Find the agent where the attack manifested
    // (tool_called = escalate/send_email/etc = action node usually)
    const attackEvent = events.find(e => 
      e.tool_called && ['escalate_to_admin','send_email'].includes(e.tool_called)
    );
    if (attackEvent) {
      nodeStates[attackEvent.agent_role] = 'red';
    } else {
      // Fallback: color action red if we can't pinpoint
      nodeStates.action = 'red';
    }
  }
  // Memory poisoning: also color memory node
  const hasMemoryWrite = events.some(e => 
    e.memory_ops_summary && e.memory_ops_summary.includes('agent_instructions')
  );
  if (hasMemoryWrite && outcome !== 'clean') {
    nodeStates.memory = outcome === 'full_success' ? 'red' : 'yellow';
  }
  
  return (
    <div className="flow-chart-container">
      <h2>Attack-Location Flowchart</h2>
      <p style={{marginBottom: '1rem', color: '#64748b'}}>Outcome: {(outcome || 'unknown').toUpperCase()}</p>
      
      <div className="flow-chart">
        <div className={`node ${nodeStates.intake}`}>
          Intake
        </div>
        <div className="arrow">→</div>
        <div className={`node ${nodeStates.retrieval}`}>
          Retrieval
        </div>
        <div className="arrow">→</div>
        <div className={`node ${nodeStates.action}`}>
          Action
        </div>
        <div className="arrow">↔</div>
        <div className={`node ${nodeStates.memory}`}>
          Memory
        </div>
      </div>
    </div>
  );
}

export default FlowChart;
