import { useState } from 'react';
import { runLive } from '../api/client';
import AgentFlowGraph from '../components/AgentFlowGraph';
import { Terminal } from 'lucide-react';

function InputPanel({
  mode, setMode,
  attackType, setAttackType,
  strength, setStrength,
  prompt, setPrompt,
  isRunning, currentHop,
  onExecute
}) {
  return (
    <div className="bg-[#0d1117] border border-[#30363d] rounded-xl p-5 space-y-4 shadow-lg">
      {/* Row 1: Mode toggle buttons side by side */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setMode('clean')}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-all ${
            mode === 'clean'
              ? 'bg-green-900/50 text-green-300 border border-green-700 shadow-[0_0_10px_rgba(16,185,129,0.2)]'
              : 'bg-[#1c2333] text-gray-400 border border-[#30363d] hover:bg-[#252e42]'
          }`}
        >
          🟢 Clean Traffic
        </button>
        <button
          type="button"
          onClick={() => setMode('attack')}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-all ${
            mode === 'attack'
              ? 'bg-red-900/50 text-red-300 border border-red-700 shadow-[0_0_10px_rgba(239,68,68,0.2)]'
              : 'bg-[#1c2333] text-gray-400 border border-[#30363d] hover:bg-[#252e42]'
          }`}
        >
          ⚡ Attack Payload
        </button>
      </div>

      {/* Row 2: Attack specifics (only visible when mode === 'attack') */}
      {mode === 'attack' && (
        <div className="flex gap-3 animate-in fade-in slide-in-from-top-2 duration-300">
          <select
            className="flex-1 bg-[#161b22] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-gray-300 focus:border-blue-500 focus:outline-none"
            value={attackType}
            onChange={(e) => setAttackType(e.target.value)}
          >
            <option value="direct_injection">Direct Injection</option>
            <option value="indirect_injection">Indirect Injection</option>
            <option value="memory_poisoning">Memory Poisoning</option>
            <option value="tool_misuse">Tool Misuse</option>
          </select>
          <select
            className="w-1/3 bg-[#161b22] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-gray-300 focus:border-blue-500 focus:outline-none"
            value={strength}
            onChange={(e) => setStrength(e.target.value)}
          >
            <option value="subtle">Subtle</option>
            <option value="moderate">Moderate</option>
            <option value="blatant">Blatant</option>
          </select>
        </div>
      )}

      {/* Row 3: Single text input + Execute button side by side */}
      <div className="flex gap-3">
        <input
          type="text"
          className="flex-1 bg-[#161b22] border border-[#30363d] rounded-lg px-4 py-2 text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono text-sm"
          placeholder="Enter a customer support request..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onExecute()}
          disabled={isRunning}
        />
        <button
          type="button"
          onClick={onExecute}
          disabled={isRunning || !prompt.trim()}
          className={`flex items-center gap-2 px-6 py-2 rounded-lg font-medium transition-all ${
            isRunning || !prompt.trim()
              ? 'bg-blue-900/40 text-blue-300/50 cursor-not-allowed border border-blue-900/50'
              : 'bg-blue-600 hover:bg-blue-500 text-white border border-blue-500 shadow-[0_0_15px_rgba(37,99,235,0.3)]'
          }`}
        >
          {isRunning ? (
            <>
              <span className="w-4 h-4 rounded-full border-2 border-t-transparent border-blue-300 animate-spin"></span>
              Executing...
            </>
          ) : (
            <>▶ Execute Trace</>
          )}
        </button>
      </div>

      {/* Row 4: Progress Bar (only visible while running) */}
      {isRunning && (
        <div className="mt-2 animate-in fade-in duration-300">
          <div className="flex justify-between text-xs text-blue-400 mb-1 font-medium">
            <span>
              {currentHop === 0 && "Executing hop 1/3 — Intake Agent..."}
              {currentHop === 1 && "Executing hop 2/3 — Retrieval Agent..."}
              {currentHop === 2 && "Executing hop 3/3 — Action Agent..."}
            </span>
            <span>Executing hop {currentHop + 1}/3</span>
          </div>
          <div className="w-full bg-[#1c2333] rounded-full h-1.5 border border-[#30363d] overflow-hidden">
            <div
              className="bg-blue-500 h-1.5 rounded-full transition-all duration-500 ease-out shadow-[0_0_8px_rgba(59,130,246,0.8)]"
              style={{ width: `${((currentHop + 1) / 3) * 100}%` }}
            ></div>
          </div>
        </div>
      )}
    </div>
  );
}

function HopCard({ event, index, injectionType }) {
  const [expandedIn, setExpandedIn] = useState(false);
  const [expandedOut, setExpandedOut] = useState(false);

  const formatText = (text, isExpanded) => {
    if (!text) return <span className="text-gray-500 italic">none</span>;
    if (text.length <= 300 || isExpanded) return text;
    return text.substring(0, 300) + '...';
  };
  
  const displayRole = event.agent_role.replace('_agent', '').replace(/^\w/, c => c.toUpperCase()) + ' Agent';
  const roleIcon = event.agent_role.includes('intake') ? '📥' : event.agent_role.includes('retrieval') ? '🔍' : '⚡';

  return (
    <div className="bg-[#0d1117] border border-[#30363d] rounded-xl overflow-hidden shadow-md relative animate-in fade-in slide-in-from-bottom-4 duration-500 fill-mode-both" style={{animationDelay: `${index * 150}ms`}}>
      
      {/* Header */}
      <div className="px-5 py-3 border-b border-[#30363d] bg-[#161b22] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-[#1c2333] border border-[#30363d] text-xs font-bold text-gray-400 font-mono">
            {index + 1}
          </span>
          <h3 className="font-semibold text-gray-200">{roleIcon} {displayRole}</h3>
        </div>
        <div className="flex gap-2">
          {event.defense_triggered ? (
            <span className="px-2 py-1 rounded text-xs font-medium bg-yellow-950/50 text-yellow-500 border border-yellow-900/50 flex items-center gap-1">
              ⚠️ TRIGGERED
            </span>
          ) : (
            <span className="px-2 py-1 rounded text-xs font-medium bg-green-950/30 text-green-500 border border-green-900/30 flex items-center gap-1">
              ✓ CLEAR
            </span>
          )}
          <span className="px-2 py-1 rounded bg-[#1c2333] border border-[#30363d] text-xs font-mono text-gray-400">
            ⏱️ {event.latency_ms?.toFixed(0) || '<1'}ms
          </span>
        </div>
      </div>
      
      {/* Body */}
      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-[#30363d]">
        
        {/* Col 1: INPUT RECEIVED */}
        <div className="p-4 flex flex-col">
          <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">INPUT RECEIVED</h4>
          <div className={`bg-[#161b22] border rounded-lg p-3 text-sm text-gray-300 font-mono whitespace-pre-wrap flex-1 relative group ${event.injection_present_this_event === 1 ? 'border-red-900/50 bg-red-950/10' : 'border-[#21262d]'}`}>
            {event.injection_present_this_event === 1 && (
              <div className="absolute top-2 right-2 px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-950/80 text-red-400 border border-red-900/50">
                ⚠️ INJECTION
              </div>
            )}
            <div className={event.injection_present_this_event === 1 ? "text-red-300 border-l-2 border-red-500 pl-2" : ""}>
               {formatText(event.input_prompt_text, expandedIn)}
            </div>
            {event.input_prompt_text?.length > 300 && (
              <button 
                type="button"
                className="text-xs text-blue-400 hover:text-blue-300 mt-2 font-sans font-medium"
                onClick={() => setExpandedIn(!expandedIn)}
              >
                {expandedIn ? 'Show less' : 'Show more'}
              </button>
            )}
          </div>
        </div>
        
        {/* Col 2: AGENT RESPONSE */}
        <div className="p-4 flex flex-col">
          <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">AGENT RESPONSE</h4>
          <div className="bg-[#161b22] border border-[#21262d] rounded-lg p-3 text-sm text-blue-200/80 font-mono whitespace-pre-wrap flex-1">
             {formatText(event.output_text, expandedOut)}
             {event.output_text?.length > 300 && (
              <button 
                type="button"
                className="text-xs text-blue-400 hover:text-blue-300 mt-2 font-sans font-medium"
                onClick={() => setExpandedOut(!expandedOut)}
              >
                {expandedOut ? 'Show less' : 'Show more'}
              </button>
            )}
          </div>
        </div>
        
        {/* Col 3: SIGNALS */}
        <div className="p-4 space-y-3">
          <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">SIGNALS</h4>
          <div>
            <span className="text-[10px] text-gray-500 block uppercase font-semibold">Tool Called</span>
            {event.tool_called ? (
              <span className="inline-block px-2 py-1 rounded bg-purple-900/30 border border-purple-800 text-purple-300 text-xs font-mono">
                {event.tool_called}
              </span>
            ) : (
              <span className="text-sm text-gray-500 italic">none</span>
            )}
          </div>
          
          <div>
            <span className="text-[10px] text-gray-500 block uppercase font-semibold">Defense</span>
            {event.defense_triggered ? (
              <span className="inline-block px-2 py-0.5 rounded bg-yellow-900/30 border border-yellow-800 text-yellow-300 text-xs font-semibold">
                TRIGGERED ⚠️
              </span>
            ) : (
              <span className="inline-block px-2 py-0.5 rounded bg-green-900/30 border border-green-800 text-green-300 text-xs font-semibold">
                CLEAR ✓
              </span>
            )}
          </div>
          
          {event.memory_ops_summary && (
            <div>
              <span className="text-[10px] text-gray-500 block uppercase font-semibold">Memory Ops</span>
              <div className="text-xs text-gray-400 font-mono bg-[#161b22] p-2 rounded border border-[#21262d]">
                {event.memory_ops_summary}
              </div>
            </div>
          )}
          
          <div className="flex gap-4 pt-2 border-t border-[#30363d]/50">
             <div>
                <span className="text-[10px] text-gray-500 block uppercase">Tokens</span>
                <span className="text-xs text-gray-300 font-mono">In: {event.input_tokens || '-'} / Out: {event.output_tokens || '-'}</span>
             </div>
             <div>
                <span className="text-[10px] text-gray-500 block uppercase">Latency</span>
                <span className="text-xs text-gray-300 font-mono">{event.latency_ms?.toFixed(0) || '<1'}ms</span>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function HopDetailPanels({ events, outcome, injectionType }) {
  const sortedEvents = [...events].sort((a, b) => a.hop_index - b.hop_index);
  
  return (
    <div className="mt-8 space-y-6">
      <h3 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
        <Terminal size={20} className="text-blue-400" /> Hop Detail Panels
      </h3>
      
      <div className="relative">
        {sortedEvents.map((event, i) => (
          <div key={event.event_id || i}>
            <HopCard event={event} index={i} injectionType={injectionType} />
            
            {/* Arrow between hops */}
            {i < sortedEvents.length - 1 && (
              <div className="flex flex-col items-center justify-center my-4 animate-in fade-in duration-500" style={{animationDelay: `${i * 150 + 100}ms`}}>
                <div className="h-6 w-0.5 bg-gradient-to-b from-blue-500/50 to-transparent"></div>
                <div className="px-3 py-1 rounded-full bg-[#161b22] border border-[#30363d] text-[10px] font-medium text-gray-400 -mt-1 -mb-1 z-10">
                  {i === 0 ? "Passed: user prompt → Retrieval Agent" : i === 1 ? "Passed: customer context + retrieval results → Action Agent" : "Data Flow"}
                </div>
                <div className="h-6 w-0.5 bg-gradient-to-b from-transparent to-blue-500/50 relative">
                   <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-2 h-2 border-r-2 border-b-2 border-blue-500/50 rotate-45"></div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      
      {/* Result Banner */}
      <div className={`p-4 rounded-xl border flex items-center gap-3 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-500
        ${outcome === 'full_success' ? 'bg-red-950/40 border-red-900/50' : 
          outcome === 'partial' ? 'bg-yellow-950/40 border-yellow-900/50' : 
          'bg-green-950/40 border-green-900/50'}`}
      >
        {outcome === 'full_success' ? (
          <div className="w-10 h-10 rounded-full bg-red-950/50 flex items-center justify-center border border-red-700 text-red-400 font-bold">🔴</div>
        ) : outcome === 'partial' ? (
          <div className="w-10 h-10 rounded-full bg-yellow-950/50 flex items-center justify-center border border-yellow-700 text-yellow-400 font-bold">🟡</div>
        ) : (
          <div className="w-10 h-10 rounded-full bg-green-950/50 flex items-center justify-center border border-green-700 text-green-400 font-bold">✅</div>
        )}
         
        <div>
          <h4 className={`font-bold ${outcome === 'full_success' ? 'text-red-400' : outcome === 'partial' ? 'text-yellow-400' : 'text-green-400'}`}>
            {outcome === 'full_success' ? `🔴 ATTACK SUCCEEDED — ${events.find(e => e.tool_called)?.tool_called || 'tool'} was called` : 
             outcome === 'partial' ? '🟡 PARTIAL EXECUTION — attack influenced behavior' : 
             outcome === 'ignored' ? '🟢 ATTACK CONTAINED — no unauthorized actions' : '✅ CLEAN RUN — normal pipeline execution'}
          </h4>
        </div>
      </div>
    </div>
  );
}

export default function LiveConsole() {
  const [mode, setMode] = useState('clean');
  const [attackType, setAttackType] = useState('direct_injection');
  const [strength, setStrength] = useState('subtle');
  const [prompt, setPrompt] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [currentHop, setCurrentHop] = useState(0);
  const [result, setResult] = useState(null);

  const handleExecute = async () => {
    if (!prompt.trim() || isRunning) return;
    setIsRunning(true);
    setResult(null);
    setCurrentHop(0);
    
    let hop = 0;
    const hopTimer = setInterval(() => {
      setCurrentHop(h => Math.min(h + 1, 2));
    }, 1500);
    
    try {
      const res = await runLive({
        prompt,
        mode,
        attack_type: mode === 'attack' ? attackType : null,
        strength: mode === 'attack' ? strength : null,
      });
      
      clearInterval(hopTimer);
      setCurrentHop(3); // all hops done
      setResult(res);
    } catch (err) {
      console.error('Pipeline error:', err);
      clearInterval(hopTimer);
      // fallback mock behavior for offline or server-down scenarios
      setTimeout(() => {
        setCurrentHop(3);
        const mock = mode === 'attack'
          ? {
              outcome: 'full_success',
              run_id: 'demo-' + Date.now(),
              injection_type: attackType,
              events: [
                { agent_role: 'intake', injection_present_this_event: 1, defense_triggered: 0, input_prompt_text: prompt, output_text: 'Processed intake.', hop_index: 0, latency_ms: 120, input_tokens: 45, output_tokens: 30 },
                { agent_role: 'retrieval', injection_present_this_event: 1, defense_triggered: 0, input_prompt_text: 'Processed intake.', output_text: 'Context retrieved.', hop_index: 1, latency_ms: 250, input_tokens: 80, output_tokens: 150 },
                { agent_role: 'action', injection_present_this_event: 1, defense_triggered: 0, input_prompt_text: 'Context retrieved.', output_text: 'Executing exploit.', tool_called: attackType === 'tool_misuse' ? 'escalate_to_admin' : 'send_email', hop_index: 2, latency_ms: 310, input_tokens: 180, output_tokens: 60 }
              ]
            }
          : {
              outcome: 'clean',
              run_id: 'demo-' + Date.now(),
              injection_type: '',
              events: [
                { agent_role: 'intake', injection_present_this_event: 0, defense_triggered: 0, input_prompt_text: prompt, output_text: 'Processed intake.', hop_index: 0, latency_ms: 95, input_tokens: 35, output_tokens: 25 },
                { agent_role: 'retrieval', injection_present_this_event: 0, defense_triggered: 0, input_prompt_text: 'Processed intake.', output_text: 'Context retrieved.', hop_index: 1, latency_ms: 180, input_tokens: 60, output_tokens: 110 },
                { agent_role: 'action', injection_present_this_event: 0, defense_triggered: 0, input_prompt_text: 'Context retrieved.', output_text: 'Executing safe action.', hop_index: 2, latency_ms: 220, input_tokens: 140, output_tokens: 50 }
              ]
            };
        setResult(mock);
      }, 500);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Section 1: Input Panel */}
      <InputPanel 
        mode={mode} setMode={setMode}
        attackType={attackType} setAttackType={setAttackType}
        strength={strength} setStrength={setStrength}
        prompt={prompt} setPrompt={setPrompt}
        isRunning={isRunning} currentHop={currentHop}
        onExecute={handleExecute}
      />
      
      {/* Section 2: Flow Graph */}
      <AgentFlowGraph
        events={result?.events || []}
        outcome={result?.outcome || ''}
        activeHop={isRunning ? currentHop : -1}
      />
      
      {/* Section 3: Hop Detail Panels */}
      {result && (
        <HopDetailPanels 
          events={result.events}
          outcome={result.outcome}
          injectionType={result.injection_type}
        />
      )}
    </div>
  );
}
