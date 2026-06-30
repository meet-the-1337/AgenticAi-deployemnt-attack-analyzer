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
  
  // A simple heuristic to color nodes based on defense and outcome
  // We check the events array to see what happened.
  let attackReachedHop = -1;
  let defenseFiredAt = null;
  
  events.forEach(e => {
    if (e.defense_triggered) {
      defenseFiredAt = e.agent_role;
      nodeStates[e.agent_role] = 'yellow';
    }
    if (e.injection_present_this_event) {
      attackReachedHop = Math.max(attackReachedHop, e.hop_index);
    }
  });
  
  if (outcome === 'full_success') {
    // Attack succeeded, mark Action node red
    nodeStates.action = 'red';
    // If memory poisoning, mark memory red
    if (events.length > 0 && events[0].run_id.includes("memory_poisoning")) {
        nodeStates.memory = 'red';
    }
  } else if (outcome === 'partial') {
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
