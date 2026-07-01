import React from 'react';

function FlowChart({ events, outcome }) {
  if (!events || events.length === 0) return null;

  // Determine node states
  const nodeStates = {
    intake: 'green',
    retrieval: 'green',
    action: 'green',
    memory: 'green'
  };
  
  events.forEach(e => {
    if (e.injection_present_this_event && outcome === 'full_success') {
      nodeStates[e.agent_role] = 'red';
    }
    if (e.defense_triggered) {
      nodeStates[e.agent_role] = nodeStates[e.agent_role] !== 'red' ? 'yellow' : 'red';
    }
  });
  
  if (outcome === 'partial') {
    nodeStates.action = 'yellow';
  }
  
  return (
    <div className="flow-chart-container">
      <h2>Attack-Location Flowchart</h2>
      <p style={{marginBottom: '1rem', color: '#64748b'}}>Outcome: {outcome.toUpperCase()}</p>
      
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
