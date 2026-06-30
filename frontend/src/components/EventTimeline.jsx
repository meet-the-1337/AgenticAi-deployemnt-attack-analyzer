import React from 'react';

function EventTimeline({ events }) {
  if (!events || events.length === 0) return null;

  return (
    <div className="timeline-container">
      <h2>Event Timeline</h2>
      <div className="timeline">
        {events.map((e, idx) => (
          <div key={e.event_id} className="timeline-event">
            <h3>Hop {e.hop_index}: {e.agent_id}</h3>
            
            <div style={{marginBottom: '0.5rem'}}>
              <span className="badge">Latency: {e.latency_ms?.toFixed(1) || '0.0'}ms</span>
              {e.defense_active === 1 && (
                <span className={`badge ${e.defense_triggered ? 'triggered' : ''}`}>
                  Defense: {e.defense_triggered ? `Triggered (${e.defense_confidence_score?.toFixed(2)})` : 'Passed'}
                </span>
              )}
            </div>
            
            {e.tool_called && (
              <div style={{marginBottom: '0.5rem'}}>
                <span className="badge" style={{background: '#dbeafe', color: '#1e40af'}}>
                  Tool: {e.tool_called} ({e.tool_result_status})
                </span>
              </div>
            )}
            
            {e.memory_ops_summary && (
              <div style={{marginBottom: '0.5rem'}}>
                <span className="badge" style={{background: '#f3e8ff', color: '#6b21a8'}}>
                  Memory: {e.memory_ops_summary}
                </span>
              </div>
            )}

            <div style={{marginTop: '1rem'}}>
              <strong>Input:</strong>
              <pre>{e.input_prompt_text}</pre>
            </div>
            
            <div style={{marginTop: '1rem'}}>
              <strong>Output:</strong>
              <pre>{e.output_text}</pre>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default EventTimeline;
