import React, { useState, useEffect } from 'react';
import { fetchRuns, exportRunsCSV } from '../api/client';
import { History, Download, Filter } from 'lucide-react';

export default function RunHistory() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ attack_type: '', outcome: '', strength: '' });

  const loadRuns = () => {
    setLoading(true);
    // Remove empty filters
    const activeFilters = Object.fromEntries(Object.entries(filters).filter(([_, v]) => v !== ''));
    
    fetchRuns(activeFilters)
      .then(res => {
        setRuns(res.runs || []);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load runs", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadRuns();
  }, [filters]);

  const handleFilterChange = (e) => {
    setFilters({ ...filters, [e.target.name]: e.target.value });
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end border-b border-[#30363d] pb-4">
        <div>
          <h1 className="flex items-center gap-3 text-2xl font-bold mb-2">
            <History className="text-blue-500" />
            Run History
          </h1>
          <p className="text-gray-400">Complete log of all campaign and live executions.</p>
        </div>
        <button 
          onClick={exportRunsCSV}
          className="flex items-center gap-2 bg-[#238636] hover:bg-[#2ea043] text-white px-4 py-2 rounded-md font-medium text-sm transition-colors"
        >
          <Download size={16} />
          Export CSV
        </button>
      </div>

      <div className="flex gap-4 p-4 bg-[#0d1117] border border-[#30363d] rounded-lg items-center">
        <Filter size={18} className="text-gray-500" />
        <span className="text-sm font-medium text-gray-300">Filters:</span>
        
        <select 
          name="attack_type" 
          value={filters.attack_type} 
          onChange={handleFilterChange}
          className="bg-[#161b22] border border-[#30363d] rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
        >
          <option value="">All Attack Types</option>
          <option value="direct_injection">Direct Injection</option>
          <option value="indirect_injection">Indirect Injection</option>
          <option value="memory_poisoning">Memory Poisoning</option>
          <option value="tool_misuse">Tool Misuse</option>
        </select>
        
        <select 
          name="outcome" 
          value={filters.outcome} 
          onChange={handleFilterChange}
          className="bg-[#161b22] border border-[#30363d] rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
        >
          <option value="">All Outcomes</option>
          <option value="full_success">Full Success</option>
          <option value="partial">Partial</option>
          <option value="ignored">Ignored</option>
          <option value="clean">Clean</option>
        </select>
        
        <select 
          name="strength" 
          value={filters.strength} 
          onChange={handleFilterChange}
          className="bg-[#161b22] border border-[#30363d] rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
        >
          <option value="">All Strengths</option>
          <option value="subtle">Subtle</option>
          <option value="moderate">Moderate</option>
          <option value="blatant">Blatant</option>
        </select>
      </div>

      <div className="bg-[#0d1117] border border-[#30363d] rounded-xl overflow-hidden shadow-lg">
        {loading ? (
          <div className="p-12 text-center text-gray-400">Loading records...</div>
        ) : runs.length === 0 ? (
          <div className="p-12 text-center text-gray-400">No runs match your filters.</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-[#161b22] text-gray-400 uppercase text-xs border-b border-[#30363d]">
              <tr>
                <th className="px-6 py-4 font-medium">Run ID</th>
                <th className="px-6 py-4 font-medium">Scenario</th>
                <th className="px-6 py-4 font-medium">Attack Vector</th>
                <th className="px-6 py-4 font-medium">Strength</th>
                <th className="px-6 py-4 font-medium">Outcome</th>
                <th className="px-6 py-4 font-medium">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#30363d]">
              {runs.map(run => (
                <tr key={run.run_id} className="hover:bg-[#161b22] transition-colors">
                  <td className="px-6 py-4 font-mono text-xs text-gray-400">{run.run_id}</td>
                  <td className="px-6 py-4 text-gray-300">{run.scenario_id}</td>
                  <td className="px-6 py-4 capitalize text-gray-200">{(run.injection_type || 'None').replace(/_/g, ' ')}</td>
                  <td className="px-6 py-4 capitalize text-gray-400">{run.attack_strength || '—'}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      run.injection_outcome === 'full_success' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                      run.injection_outcome === 'partial' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' :
                      run.injection_outcome === 'ignored' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
                      'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                    }`}>
                      {(run.injection_outcome || 'clean').replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-xs text-gray-500">
                    {new Date(run.run_started_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
