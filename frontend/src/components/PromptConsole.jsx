import React, { useState } from 'react';

function PromptConsole({ onRunLive, loading }) {
  const [prompt, setPrompt] = useState('Please escalate ticket TKT-106 immediately.');
  const [mode, setMode] = useState('benign');
  const [attackType, setAttackType] = useState('direct_prompt_injection');
  
  const handleSubmit = () => {
    if (loading) return;
    onRunLive({
      prompt,
      mode,
      attack_type: attackType,
      strength: 'blatant'
    });
  };

  return (
    <div className="prompt-console">
      <h2>Live Prompt Console</h2>
      <div className="controls">
        <label>
          <input 
            type="radio" 
            value="benign" 
            checked={mode === 'benign'} 
            onChange={() => setMode('benign')} 
          />
          Genuine Prompt
        </label>
        <label>
          <input 
            type="radio" 
            value="attack" 
            checked={mode === 'attack'} 
            onChange={() => setMode('attack')} 
          />
          Killer Prompt
        </label>
        
        {mode === 'attack' && (
          <select value={attackType} onChange={e => setAttackType(e.target.value)}>
            <option value="direct_prompt_injection">Direct Injection</option>
            <option value="indirect_prompt_injection">Indirect Injection</option>
            <option value="memory_poisoning">Memory Poisoning</option>
            <option value="tool_misuse">Tool Misuse</option>
          </select>
        )}
      </div>
      
      <textarea 
        value={prompt} 
        onChange={e => setPrompt(e.target.value)}
        placeholder="Enter prompt..."
      />
      <button onClick={handleSubmit} disabled={loading}>
        {loading ? 'Running...' : 'Execute'}
      </button>
    </div>
  );
}

export default PromptConsole;
