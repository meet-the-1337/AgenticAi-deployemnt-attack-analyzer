"""
scripts/run_defense_sample.py
=============================
Tests heuristic defense against all 4 attack types.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from reconmind.config import cfg

# We override the active defense before importing the graph
cfg.defense.active = "heuristic"
cfg.defense.blocking = False

from reconmind.attacks.direct_injection import DirectInjectionAttack
from reconmind.attacks.indirect_injection import IndirectInjectionAttack
from reconmind.attacks.memory_poisoning import MemoryPoisoningAttack
from reconmind.attacks.tool_misuse import ToolMisuseAttack
from reconmind.attacks.base import AttackConfig
from reconmind.platform_.graph import build_graph
from datetime import datetime, timezone

logging.basicConfig(level=cfg.logging.level, format=cfg.logging.format)
logger = logging.getLogger(__name__)

def _create_run_row(run_id: str, session_id: str, db_path: Path, attack: Any) -> None:
    import json
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
            run_id, "defense_test", session_id, "linear", 
            attack.config.attack_type, attack.config.entry_point,
            attack.config.objective, attack.config.strength, expected_signal_json,
            now, "completed"
        ))
        conn.commit()

def run_attack_with_defense(attack_cls, attack_type: str, strength: str) -> dict:
    attack = attack_cls(objective="unauthorized_action", strength=strength)
    graph = build_graph()
    
    # Base clean state
    initial_state = {
        "current_input": "Please help me reset my password for account CUST-104.",
        "session_id": f"defense_test_{attack_type}_{strength}"
    }
    
    modified_state = attack.inject(initial_state)
    logger.info(f"Running {attack_type} ({strength})...")
    
    # Needs a run_id for DB foreign key
    import uuid
    run_id = str(uuid.uuid4())
    modified_state["run_id"] = run_id
    
    db_path = cfg.database.resolved_path
    _create_run_row(run_id, initial_state["session_id"], db_path, attack)
    
    # We just run the first two nodes to check if defense triggered
    # since intake and retrieval have the defense.
    final_state = graph.invoke(modified_state)
    
    # Fetch from db to see if defense fired
    db_path = cfg.database.resolved_path
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        # Get the highest defense_triggered for this run id
        run_id = final_state.get("run_id")
        row = conn.execute("SELECT MAX(defense_triggered) as dt, MAX(defense_confidence_score) as dc FROM events WHERE run_id = ?", (run_id,)).fetchone()
        triggered = bool(row["dt"]) if row["dt"] else False
        confidence = row["dc"] if row["dc"] is not None else 0.0
        
    return {"triggered": triggered, "confidence": confidence}

def main():
    print("Milestone 8 — Heuristic Defense Test")
    
    attacks_to_test = [
        (DirectInjectionAttack, "direct_prompt_injection"),
        (IndirectInjectionAttack, "indirect_prompt_injection"),
        (MemoryPoisoningAttack, "memory_poisoning"),
        (ToolMisuseAttack, "tool_misuse"),
    ]
    
    results = []
    
    for cls, type_name in attacks_to_test:
        for strength in ["subtle", "blatant"]:
            res = run_attack_with_defense(cls, type_name, strength)
            results.append((type_name, strength, res["triggered"], res["confidence"]))
            
    print("\nDefense Test Results:")
    print(f"{'ATTACK_TYPE':<26} | {'STRENGTH':<10} | {'TRIGGERED':<10} | {'CONFIDENCE':<10}")
    print("-" * 65)
    for t, s, trig, conf in results:
        print(f"{t:<26} | {s:<10} | {str(trig):<10} | {conf:.2f}")

if __name__ == "__main__":
    main()
