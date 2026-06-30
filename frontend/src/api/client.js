const API_BASE = 'http://127.0.0.1:8000';

export async function fetchRuns() {
  const res = await fetch(`${API_BASE}/runs`);
  if (!res.ok) throw new Error('Failed to fetch runs');
  return res.json();
}

export async function fetchRunEvents(runId) {
  const res = await fetch(`${API_BASE}/runs/${runId}/events`);
  if (!res.ok) throw new Error('Failed to fetch events');
  return res.json();
}

export async function runLive(data) {
  const res = await fetch(`${API_BASE}/run/live`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error('Failed to run live pipeline');
  return res.json();
}
