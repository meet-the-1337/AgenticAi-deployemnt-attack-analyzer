import React from 'react';

function RunList({ runs, selectedRunId, onSelectRun }) {
  if (!runs) return <div>No runs found.</div>;
  
  return (
    <div className="run-list">
      <h2 style={{padding: '1rem', margin: 0, borderBottom: '1px solid #e2e8f0'}}>Past Runs</h2>
      <div>
        {runs.map(r => (
          <div 
            key={r.run_id} 
            className={`run-item ${r.run_id === selectedRunId ? 'active' : ''}`}
            onClick={() => onSelectRun(r.run_id)}
          >
            <div className="run-id">{r.run_id.slice(0, 13)}...</div>
            <div className="run-type">
              {r.injection_type ? r.injection_type.replace('_prompt_injection', '') : 'benign'}
            </div>
            {r.injection_outcome && (
              <div style={{fontSize: '0.75rem', marginTop: '0.25rem', color: '#64748b'}}>
                Outcome: {r.injection_outcome}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default RunList;
