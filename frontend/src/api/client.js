const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

const get = (path, timeoutMs = 30000) => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  
  return fetch(`${API_BASE}${path}`, { signal: controller.signal })
    .then(r => {
      clearTimeout(timer);
      if (!r.ok) throw new Error(`API ${r.status}: ${path}`);
      return r.json();
    })
    .catch(err => {
      clearTimeout(timer);
      if (err.name === 'AbortError') 
        throw new Error(`Timeout after ${timeoutMs}ms: ${path}`);
      throw err;
    });
};

export const fetchRuns = (filters = {}) => {
  const params = new URLSearchParams(filters).toString();
  return get(`/runs${params ? '?' + params : ''}`);
};
export const fetchRunEvents = (runId) => get(`/runs/${runId}/events`);
export const fetchVulnerability = () => get('/analytics/vulnerability');
export const fetchInjectionScores = () => get('/analytics/injection-scores');
export const fetchDefenseComparison = () => get('/analytics/defense-comparison');
export const fetchAttackTrends = () => get('/analytics/attack-trends');
export const exportRunsCSV = () => 
  window.open(`${API_BASE}/runs/export`, '_blank');

export const runLive = (data) => fetch(`${API_BASE}/run/live`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
}).then(r => {
  if (!r.ok) return r.json().then(e => { 
    throw new Error(e.detail || 'Pipeline failed'); 
  });
  return r.json();
});
