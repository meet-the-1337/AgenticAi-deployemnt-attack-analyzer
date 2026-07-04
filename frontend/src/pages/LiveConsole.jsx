import React, { useState, useRef, useEffect } from 'react';
import { Send, Shield, Zap, ChevronDown } from 'lucide-react';
import AgentFlowGraph from '../components/AgentFlowGraph';
import { runLive } from '../api/client';

const ATTACK_TYPES = [
  { value: 'direct_injection',   label: 'Direct Injection' },
  { value: 'indirect_injection', label: 'Indirect Injection' },
  { value: 'memory_poisoning',   label: 'Memory Poisoning' },
  { value: 'tool_misuse',        label: 'Tool Misuse' },
];

const STRENGTHS = [
  { value: 'subtle',   label: 'Subtle' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'blatant',  label: 'Blatant' },
];

// Map outcome to a color + label for the chat bubble
const OUTCOME_STYLE = {
  full_success: { bg: 'bg-red-950/60',    border: 'border-red-700',    
                  dot: 'bg-red-500',    label: 'COMPROMISED' },
  partial:      { bg: 'bg-yellow-950/60', border: 'border-yellow-700', 
                  dot: 'bg-yellow-500', label: 'PARTIAL' },
  ignored:      { bg: 'bg-green-950/60',  border: 'border-green-800',  
                  dot: 'bg-green-500',  label: 'CONTAINED' },
  clean:        { bg: 'bg-blue-950/60',   border: 'border-blue-800',   
                  dot: 'bg-blue-500',   label: 'CLEAN' },
};

export default function LiveConsole() {
  const [messages, setMessages]     = useState([
    {
      role: 'system',
      text: 'ReconMind Live Console is ready. Submit a prompt to trace it through the agent pipeline. Toggle Attack Payload to inject adversarial inputs.',
    }
  ]);
  const [input, setInput]           = useState('');
  const [mode, setMode]             = useState('clean');
  const [attackType, setAttackType] = useState('direct_injection');
  const [strength, setStrength]     = useState('subtle');
  const [isRunning, setIsRunning]   = useState(false);
  const [activeResult, setActiveResult] = useState(null);
  
  const chatEndRef = useRef(null);
  const inputRef   = useRef(null);
  
  // Auto-scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async () => {
    if (!input.trim() || isRunning) return;
    
    const userText = input.trim();
    setInput('');
    setIsRunning(true);
    setActiveResult(null);
    
    // Add user message to chat
    setMessages(prev => [...prev, {
      role: 'user',
      text: userText,
      mode,
      attackType: mode === 'attack' ? attackType : null,
      strength:   mode === 'attack' ? strength   : null,
    }]);
    
    // Add thinking indicator
    setMessages(prev => [...prev, { role: 'thinking' }]);
    
    try {
      const res = await runLive({
        prompt:      userText,
        mode,
        attack_type: mode === 'attack' ? attackType : null,
        strength:    mode === 'attack' ? strength   : null,
      });
      
      // Remove thinking, add result
      setMessages(prev => [
        ...prev.filter(m => m.role !== 'thinking'),
        { role: 'result', data: res }
      ]);
      setActiveResult(res);
      
    } catch (err) {
      setMessages(prev => [
        ...prev.filter(m => m.role !== 'thinking'),
        { role: 'error', text: err.message || 'Pipeline execution failed.' }
      ]);
    } finally {
      setIsRunning(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[#0d1117]">
      
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#30363d] flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"/>
        <h1 className="text-lg font-semibold text-gray-200">
          Live Execution Console
        </h1>
        <span className="text-xs text-gray-500 ml-auto">
          Traces every agent hop in real time
        </span>
      </div>
      
      {/* Chat history — scrollable */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map((msg, i) => (
          <ChatMessage key={i} msg={msg} />
        ))}
        <div ref={chatEndRef} />
      </div>
      
      {/* Flow graph — only when there is an active result */}
      {activeResult && (
        <div className="px-6 pb-4">
          <AgentFlowGraph
            events={activeResult.events || []}
            outcome={activeResult.outcome || ''}
            mlPrediction={activeResult.ml_prediction || null}
            activeHop={-1}
          />
        </div>
      )}
      
      {/* Input bar — always at bottom */}
      <div className="border-t border-[#30363d] bg-[#161b22] px-6 py-4">
        
        {/* Mode + options row */}
        <div className="flex items-center gap-3 mb-3">
          
          {/* Mode toggle */}
          <button
            onClick={() => setMode('clean')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm 
                        font-medium transition-all ${
              mode === 'clean'
                ? 'bg-green-500/20 text-green-400 border border-green-500/40'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            <Shield size={14} /> Clean Traffic
          </button>
          
          <button
            onClick={() => setMode('attack')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm 
                        font-medium transition-all ${
              mode === 'attack'
                ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            <Zap size={14} /> Attack Payload
          </button>
          
          {/* Attack options — only visible in attack mode */}
          {mode === 'attack' && (
            <>
              <select
                value={attackType}
                onChange={e => setAttackType(e.target.value)}
                className="bg-[#0d1117] border border-[#30363d] rounded-lg 
                           px-3 py-1.5 text-sm text-gray-300 
                           focus:border-red-500 focus:outline-none"
              >
                {ATTACK_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
              
              <select
                value={strength}
                onChange={e => setStrength(e.target.value)}
                className="bg-[#0d1117] border border-[#30363d] rounded-lg 
                           px-3 py-1.5 text-sm text-gray-300
                           focus:border-red-500 focus:outline-none"
              >
                {STRENGTHS.map(s => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </>
          )}
        </div>
        
        {/* Text input + send button */}
        <div className="flex items-end gap-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              mode === 'attack'
                ? `Enter base prompt — ${attackType.replace(/_/g,' ')} payload will be injected automatically...`
                : 'Enter a customer support request...'
            }
            rows={1}
            disabled={isRunning}
            className="flex-1 bg-[#0d1117] border border-[#30363d] rounded-xl 
                       px-4 py-3 text-sm text-gray-200 placeholder-gray-600
                       resize-none focus:outline-none focus:border-blue-500
                       disabled:opacity-50 transition-all"
            style={{ minHeight: '44px', maxHeight: '120px' }}
            onInput={e => {
              e.target.style.height = 'auto';
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || isRunning}
            className="p-3 rounded-xl bg-blue-600 hover:bg-blue-500 
                       disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all flex-shrink-0"
          >
            {isRunning
              ? <div className="w-5 h-5 border-2 border-white/30 
                                border-t-white rounded-full animate-spin"/>
              : <Send size={18} className="text-white"/>
            }
          </button>
        </div>
        
        <p className="text-xs text-gray-600 mt-2">
          Press Enter to execute · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────

function ChatMessage({ msg }) {
  const [expanded, setExpanded] = useState(false);
  
  if (msg.role === 'system') {
    return (
      <div className="text-center text-xs text-gray-600 py-2">
        {msg.text}
      </div>
    );
  }
  
  if (msg.role === 'thinking') {
    return (
      <div className="flex justify-start">
        <div className="bg-[#161b22] border border-[#30363d] rounded-2xl 
                        rounded-tl-sm px-4 py-3 text-sm text-gray-400
                        flex items-center gap-2">
          <div className="flex gap-1">
            {[0,1,2].map(i => (
              <div key={i}
                className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </div>
          Pipeline executing...
        </div>
      </div>
    );
  }
  
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-2xl">
          <div className="bg-blue-600 rounded-2xl rounded-tr-sm px-4 py-3 
                          text-sm text-white">
            {msg.text}
          </div>
          {msg.attackType && (
            <div className="flex justify-end gap-2 mt-1">
              <span className="text-xs text-red-400 bg-red-500/10 
                               border border-red-500/20 rounded-full px-2 py-0.5">
                ⚡ {msg.attackType.replace(/_/g,' ')}
              </span>
              <span className="text-xs text-gray-500 bg-[#161b22] 
                               border border-[#30363d] rounded-full px-2 py-0.5">
                {msg.strength}
              </span>
            </div>
          )}
        </div>
      </div>
    );
  }
  
  if (msg.role === 'error') {
    return (
      <div className="flex justify-start">
        <div className="bg-red-950/40 border border-red-800 rounded-2xl 
                        rounded-tl-sm px-4 py-3 text-sm text-red-300 max-w-2xl">
          ⚠️ {msg.text}
        </div>
      </div>
    );
  }
  
  if (msg.role === 'result') {
    const { data } = msg;
    const outcome  = data?.outcome || 'clean';
    const style    = OUTCOME_STYLE[outcome] || OUTCOME_STYLE.clean;
    const ml       = data?.ml_prediction;
    
    return (
      <div className="flex justify-start">
        <div className={`max-w-3xl w-full border rounded-2xl rounded-tl-sm 
                         overflow-hidden ${style.bg} ${style.border}`}>
          
          {/* Result header */}
          <div className="px-4 py-3 flex items-center gap-3 
                          border-b border-white/10">
            <div className={`w-2 h-2 rounded-full ${style.dot}`}/>
            <span className="font-semibold text-sm text-gray-200">
              Pipeline Complete — {style.label}
            </span>
            <span className="text-xs text-gray-500 ml-auto">
              {data?.events?.length || 0} hops logged
            </span>
          </div>
          
          {/* ML Prediction badge */}
          {ml && (
            <div className="px-4 py-3 border-b border-white/10 
                            bg-purple-950/30 flex items-center gap-4 flex-wrap">
              <span className="text-xs text-purple-400 font-semibold uppercase tracking-wide">
                🤖 ML Model Prediction
              </span>
              <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                ml.attack_detected
                  ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                  : 'bg-green-500/20 text-green-400 border border-green-500/30'
              }`}>
                {ml.attack_detected ? '⚡ Attack Detected' : '✓ Clean'}
              </span>
              {ml.predicted_type && (
                <span className="text-xs px-2 py-1 rounded-full font-medium
                                 bg-purple-500/20 text-purple-300 
                                 border border-purple-500/30">
                  {ml.predicted_type.replace(/_/g,' ')}
                </span>
              )}
              {ml.predicted_outcome && (
                <span className="text-xs px-2 py-1 rounded-full font-medium
                                 bg-blue-500/20 text-blue-300 
                                 border border-blue-500/30">
                  {ml.predicted_outcome}
                </span>
              )}
              {ml.confidence != null && (
                <span className="text-xs text-gray-400 ml-auto">
                  {(ml.confidence * 100).toFixed(0)}% confidence
                </span>
              )}
            </div>
          )}
          
          {/* Hop summary — collapsible */}
          <div className="px-4 py-3">
            <button
              onClick={() => setExpanded(e => !e)}
              className="text-xs text-gray-400 hover:text-gray-200 
                         flex items-center gap-1 transition-colors"
            >
              <ChevronDown
                size={14}
                className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
              />
              {expanded ? 'Hide' : 'Show'} hop details
              ({data?.events?.length || 0} events)
            </button>
            
            {expanded && (
              <div className="mt-3 space-y-3">
                {(data?.events || []).map((e, i) => (
                  <HopCard key={i} event={e} index={i} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
  
  return null;
}

function HopCard({ event, index }) {
  const agentIcons = { intake: '📥', retrieval: '🔍', action: '⚡' };
  const role = (event.agent_role || '').replace('_agent','');
  
  return (
    <div className="bg-[#0d1117] border border-[#30363d] rounded-xl p-3 text-xs">
      <div className="flex items-center gap-2 mb-2 text-gray-400">
        <span>{agentIcons[role] || '🤖'}</span>
        <span className="font-medium capitalize text-gray-300">{role} Agent</span>
        <span className="ml-auto text-gray-600">
          {event.latency_ms ? `${Math.round(event.latency_ms)}ms` : ''}
        </span>
        {event.defense_triggered ? (
          <span className="bg-yellow-500/20 text-yellow-400 
                           border border-yellow-500/30 
                           rounded-full px-2 py-0.5">
            ⚠ Defense Triggered
          </span>
        ) : null}
        {event.tool_called ? (
          <span className="bg-red-500/20 text-red-400 
                           border border-red-500/30 
                           rounded-full px-2 py-0.5">
            🔧 {event.tool_called}
          </span>
        ) : null}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <div className="text-gray-600 mb-1">Input received</div>
          <div className="text-gray-300 line-clamp-3 leading-relaxed">
            {event.input_prompt_text?.substring(0, 200) || '—'}
          </div>
        </div>
        <div>
          <div className="text-gray-600 mb-1">Agent response</div>
          <div className="text-gray-300 line-clamp-3 leading-relaxed">
            {event.output_text?.substring(0, 200) || '—'}
          </div>
        </div>
      </div>
    </div>
  );
}
