import React, { useState, useEffect } from 'react';
import PromptConsole from './components/PromptConsole';
import FlowChart from './components/FlowChart';
import RunList from './components/RunList';
import EventTimeline from './components/EventTimeline';
import { fetchRuns, fetchRunEvents, runLive } from './api/client';
import './index.css';

function App() {
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [events, setEvents] = useState([]);
  const [outcome, setOutcome] = useState('unknown');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadRuns();
  }, []);

  const loadRuns = async () => {
    const data = await fetchRuns();
    setRuns(data.runs || []);
  };

  const handleSelectRun = async (runId) => {
    setSelectedRunId(runId);
    setLoading(true);
    try {
      const data = await fetchRunEvents(runId);
      setEvents(data.events || []);
      setOutcome(data.outcome || 'unknown');
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleLiveRun = async (promptData) => {
    setLoading(true);
    setSelectedRunId(null);
    setEvents([]);
    setOutcome('unknown');
    
    try {
      const data = await runLive(promptData);
      setEvents(data.events || []);
      setOutcome(data.outcome || 'unknown');
      setSelectedRunId(data.run_id);
      loadRuns();
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>ReconMind Dashboard</h1>
      </header>
      <div className="main-layout">
        <aside className="sidebar">
          <RunList runs={runs} selectedRunId={selectedRunId} onSelectRun={handleSelectRun} />
        </aside>
        <main className="content">
          <PromptConsole onRunLive={handleLiveRun} loading={loading} />
          
          {loading && <div className="loading-state">Running pipeline... this will take a few seconds as Qwen processes the request.</div>}
          
          {selectedRunId && !loading && (
            <>
              <FlowChart events={events} outcome={outcome} />
              <EventTimeline events={events} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
