const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

const get = async (livePath, staticPath) => {
  const baseUrl = import.meta.env.BASE_URL || '';
  // Clean slash mapping
  const normalizedBase = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
  
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000); // 8s timeout for live API check
    const response = await fetch(`${API_BASE}${livePath}`, { signal: controller.signal });
    clearTimeout(timer);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (err) {
    console.warn(`Live API ${livePath} unreachable. Falling back to static route: /api${staticPath}`, err);
    const fallbackResponse = await fetch(`${normalizedBase}/api${staticPath}`);
    if (!fallbackResponse.ok) throw new Error(`Static route failed: ${staticPath}`);
    return await fallbackResponse.json();
  }
};

export const fetchRuns = (filters = {}) => {
  // If filters are active, live API is required; otherwise fallback to static runs.json
  const params = new URLSearchParams(filters).toString();
  if (params) {
    return get(`/runs?${params}`, `/runs.json`).then(res => {
      // client-side filter fallback if static JSON was loaded
      if (res.runs && Object.keys(filters).length > 0) {
        let filtered = [...res.runs];
        if (filters.attack_type) {
          filtered = filtered.filter(r => r.injection_type === filters.attack_type);
        }
        if (filters.outcome) {
          filtered = filtered.filter(r => r.injection_outcome === filters.outcome);
        }
        if (filters.strength) {
          filtered = filtered.filter(r => r.attack_strength === filters.strength);
        }
        return { runs: filtered };
      }
      return res;
    });
  }
  return get('/runs', '/runs.json');
};

export const fetchEnrichedRuns = (limit = 15) => {
  return get(`/runs/enriched?limit=${limit}`, '/runs_enriched.json');
};

export const fetchVulnerabilitySummary = () => {
  return get('/analytics/vulnerability-summary', '/vulnerability_summary.json');
};

export const fetchRunEvents = (runId) => {
  return get(`/runs/${runId}/events`, `/runs/${runId}.json`);
};

export const fetchVulnerability = () => {
  return get('/analytics/vulnerability', '/vulnerability.json');
};

export const fetchInjectionScores = () => {
  return get('/analytics/injection-scores', '/injection_scores.json');
};

export const fetchDefenseComparison = () => {
  return get('/analytics/defense-comparison', '/defense_comparison.json');
};

export const fetchAttackTrends = () => {
  return get('/analytics/attack-trends', '/attack_trends.json');
};

export const exportRunsCSV = () => {
  window.open(`${API_BASE}/runs/export`, '_blank');
};

export const runLive = async (data) => {
  try {
    const response = await fetch(`${API_BASE}/run/live`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!response.ok) {
      const errDetail = await response.json();
      throw new Error(errDetail.detail || 'Pipeline failed');
    }
    return await response.json();
  } catch (err) {
    console.error('runLive request failed', err);
    throw err; // propagates to let the page run its simulated mock demo fallback
  }
};
