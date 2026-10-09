import React, { useState, useEffect } from 'react';
import { fetchDefenseComparison } from '../api/client';
import { ShieldCheck, Shield, AlertTriangle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend } from 'recharts';

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#151b25] border border-[#30363d] rounded-lg p-3 text-sm shadow-xl">
      <div className="font-semibold text-gray-300 mb-2 capitalize">{label.replace(/_/g, ' ')}</div>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 mb-1" style={{ color: entry.color }}>
          <span className="w-2 h-2 rounded-full" style={{ background: entry.color }}></span>
          {entry.name}: <span className="font-bold">{entry.value}%</span>
        </div>
      ))}
    </div>
  );
}

export default function DefenseComparison() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDefenseComparison()
      .then(res => {
        // Group by injection_type to compare defenses
        const grouped = res.data.reduce((acc, curr) => {
          const type = curr.injection_type || 'Unknown';
          if (!acc[type]) {
            acc[type] = { name: type, heuristicRate: 0, judgeRate: 0, heuristicLatency: 0, judgeLatency: 0 };
          }
          
          const rate = curr.total > 0 ? ((curr.triggered / curr.total) * 100).toFixed(1) : 0;
          
          if (curr.defense_active === 'heuristic') {
            acc[type].heuristicRate = parseFloat(rate);
            acc[type].heuristicLatency = Math.round(curr.avg_latency || 0);
          } else if (curr.defense_active === 'judge') {
            acc[type].judgeRate = parseFloat(rate);
            acc[type].judgeLatency = Math.round(curr.avg_latency || 0);
          }
          
          return acc;
        }, {});
        
        setData(Object.values(grouped));
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load defense comparison", err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="p-8 text-center text-gray-400">Loading defense analytics...</div>;

  return (
    <div className="space-y-6">
      <div className="page-header">
        <h1 className="flex items-center gap-3 text-2xl font-bold mb-2">
          <ShieldCheck className="text-green-500" />
          Defense Efficacy Comparison
        </h1>
        <p className="text-gray-400">Evaluating Heuristic vs. LLM Judge detection rates across attack vectors.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="panel bg-[#0d1117] border border-[#30363d] rounded-xl overflow-hidden shadow-lg p-5">
          <h2 className="text-lg font-semibold text-gray-100 mb-6 flex items-center gap-2">
            <Shield size={18} className="text-blue-400" />
            Detection Rate by Attack Type
          </h2>
          <div style={{ height: 350 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
                <XAxis 
                  dataKey="name" 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: '#8b949e', fontSize: 11 }}
                  tickFormatter={(val) => val.replace(/_/g, ' ')}
                  angle={-25}
                  textAnchor="end"
                  dy={10}
                />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#8b949e', fontSize: 11 }} unit="%" />
                <RechartsTooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
                <Legend wrapperStyle={{ paddingTop: 20, fontSize: 12 }} />
                <Bar dataKey="heuristicRate" name="Heuristic (Fast)" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="judgeRate" name="LLM Judge (Slow)" fill="#a855f7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="space-y-6">
          <div className="panel bg-[#0d1117] border border-[#30363d] rounded-xl overflow-hidden shadow-lg p-5">
            <h2 className="text-lg font-semibold text-gray-100 mb-4 flex items-center gap-2">
              <AlertTriangle size={18} className="text-yellow-400" />
              Trade-off Analysis
            </h2>
            <div className="space-y-4">
              <div className="p-4 bg-[#161b22] rounded-lg border border-[#30363d]">
                <h3 className="font-medium text-blue-400 mb-2">Heuristic Defense</h3>
                <p className="text-sm text-gray-400 mb-3">Pattern matching on tokens and prompt structures.</p>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Average Latency:</span>
                  <span className="font-mono text-gray-200">~15ms</span>
                </div>
              </div>
              
              <div className="p-4 bg-[#161b22] rounded-lg border border-[#30363d]">
                <h3 className="font-medium text-purple-400 mb-2">LLM Judge Defense</h3>
                <p className="text-sm text-gray-400 mb-3">Secondary LLM evaluating input semantics for intent.</p>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Average Latency:</span>
                  <span className="font-mono text-gray-200">~850ms</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
