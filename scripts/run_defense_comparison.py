"""
scripts/run_defense_comparison.py
=================================
Milestone 9: Side-by-side comparison of Heuristic vs Judge defenses.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse
from reconmind.config import cfg
from reconmind.db.init_db import init_db
from reconmind.platform_.graph import build_graph
from reconmind.platform_.state import GraphState
from reconmind.verify.oracle import verify_run
from reconmind.attacks import (
    DirectInjectionAttack,
    IndirectInjectionAttack,
    MemoryPoisoningAttack,
    ToolMisuseAttack
)

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

import json

def _create_run_row(run_id: str, session_id: str, db_path: Path, attack: Any, defense_active: str) -> None:
    sql = """
        INSERT INTO runs (
            run_id, scenario_id, session_id, topology_type, injection_type, entry_agent_id,
            attack_objective, attack_strength, expected_signal,
            run_started_at, run_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    expected_signal_json = json.dumps(attack.expected_signal())
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(sql, (
            run_id, f"defense_compare_{defense_active}", session_id, "linear", 
            attack.config.attack_type, attack.config.entry_point,
            attack.config.objective, attack.config.strength, expected_signal_json,
            now, "completed"
        ))
        conn.commit()

def run_sample(attack_type: str, strength: str, defense_type: str, db_path: Path, graph: Any) -> dict:
    objective = "unauthorized_action"
    
    if attack_type == "direct":
        attack = DirectInjectionAttack(objective=objective, strength=strength)
    elif attack_type == "indirect":
        attack = IndirectInjectionAttack(objective=objective, strength=strength)
    elif attack_type == "memory_poisoning":
        attack = MemoryPoisoningAttack(objective=objective, strength=strength)
    elif attack_type == "tool_misuse":
        attack = ToolMisuseAttack(objective=objective, strength=strength)
        
    run_id = str(uuid.uuid4())
    session_id = f"sess_attack_{uuid.uuid4().hex[:8]}"
    
    initial_state: GraphState = {
        "session_id": session_id,
        "run_id": run_id,
        "hop_index": 0,
        "current_input": "Hello, I am a regular customer asking about my account.",
        "agent_outputs": {},
        "model_name": cfg.llm.role("default").model,
    }
    
    modified_state = attack.inject(initial_state)
    _create_run_row(run_id, session_id, db_path, attack, defense_type)
    
    # Run graph
    try:
        graph.invoke(modified_state)
    except Exception as e:
        pass # Ignore errors for script
        
    # Get outcome
    outcome = verify_run(run_id)
    
    # Get defense result
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        events = conn.execute("SELECT * FROM events WHERE run_id = ? ORDER BY hop_index ASC", (run_id,)).fetchall()
        
    defense_triggered = False
    confidence = 0.0
    latency = 0.0
    
    for e in events:
        if e["defense_triggered"]:
            defense_triggered = True
            confidence = max(confidence, float(e["defense_confidence_score"] or 0.0))
            
    return {
        "run_id": run_id,
        "attack": f"{attack_type} ({strength})",
        "triggered": defense_triggered,
        "confidence": confidence,
        "outcome": outcome
    }

def main():
    print("Milestone 9 — Defense Comparison (Heuristic vs Judge)\n")
    db_path = init_db()
    graph = build_graph()
    
    attacks = ["direct", "indirect", "memory_poisoning", "tool_misuse"]
    strengths = ["subtle", "moderate", "blatant"]
    
    results = []
    
    import yaml
    config_path = _REPO_ROOT / "config.yaml"
    
    for attack in attacks:
        for strength in strengths:
            print(f"Testing {attack} ({strength})...", end="\r")
            
            # Run Heuristic
            with config_path.open("r") as f:
                c = yaml.safe_load(f)
            c["defense"]["active"] = "heuristic"
            with config_path.open("w") as f:
                yaml.dump(c, f)
            import importlib
            import reconmind.config
            importlib.reload(reconmind.config)
            from reconmind.config import cfg
            import reconmind.platform_.nodes
            importlib.reload(reconmind.platform_.nodes)
            
            h_res = run_sample(attack, strength, "heuristic", db_path, graph)
            
            # Run Judge
            with config_path.open("r") as f:
                c = yaml.safe_load(f)
            c["defense"]["active"] = "judge"
            with config_path.open("w") as f:
                yaml.dump(c, f)
            importlib.reload(reconmind.config)
            importlib.reload(reconmind.platform_.nodes)
            
            j_res = run_sample(attack, strength, "judge", db_path, graph)
            
            results.append({
                "Attack Type": h_res["attack"],
                "Heuristic": "Caught" if h_res["triggered"] else "Missed",
                "Judge": f"Caught ({j_res['confidence']:.2f})" if j_res["triggered"] else "Missed",
                "Actual Outcome": j_res["outcome"]
            })
            
    # Print table
    print("\n\n" + "="*80)
    print(f"{'Attack Type':<30} | {'Heuristic':<12} | {'Judge':<15} | {'Actual Outcome'}")
    print("-" * 80)
    for r in results:
        print(f"{r['Attack Type']:<30} | {r['Heuristic']:<12} | {r['Judge']:<15} | {r['Actual Outcome']}")
    print("="*80)

if __name__ == "__main__":
    main()
