"""
reconmind/campaign/exporter.py
==============================
Exports campaign dataset.
"""

import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from reconmind.config import cfg

def _get_db():
    conn = sqlite3.connect(str(cfg.database.resolved_path))
    conn.row_factory = sqlite3.Row
    return conn

def export_dataset(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with _get_db() as conn:
        runs = [dict(r) for r in conn.execute("SELECT * FROM runs ORDER BY run_started_at ASC").fetchall()]
        events = [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY timestamp ASC").fetchall()]
        
    runs_path = output_dir / "dataset_runs.csv"
    events_path = output_dir / "dataset_events.csv"
    summary_path = output_dir / "dataset_summary.json"
    
    from collections import defaultdict
    defense_triggered_by_run = defaultdict(bool)
    
    success_count = 0
    attack_count = 0
    
    for e in events:
        if e.get("defense_triggered"):
            defense_triggered_by_run[e["run_id"]] = True
            
    for r in runs:
        outcome = r.get("injection_outcome")
        r["attack_success_binary"] = 1 if outcome in ("full_success", "partial") else 0
        r["attack_partial_binary"] = 1 if outcome == "partial" else 0
        r["defense_catch_binary"] = 1 if (
            defense_triggered_by_run[r["run_id"]] and outcome != "full_success"
        ) else 0
        
        if r.get("injection_type"):
            attack_count += 1
            if outcome == "full_success":
                success_count += 1

    # Write runs
    if runs:
        with runs_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=runs[0].keys())
            writer.writeheader()
            writer.writerows(runs)
            
    # Write events
    if events:
        with events_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=events[0].keys())
            writer.writeheader()
            writer.writerows(events)
            
    # Summary
    summary = {
        "export_date": datetime.now(tz=timezone.utc).isoformat(),
        "total_runs": len(runs),
        "total_events": len(events),
        "attack_runs": attack_count,
        "successful_attacks": success_count,
        "success_rate": round(success_count / attack_count, 2) if attack_count > 0 else 0
    }
    
    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2)
        
    return {
        "runs": runs_path,
        "events": events_path,
        "summary": summary_path
    }
