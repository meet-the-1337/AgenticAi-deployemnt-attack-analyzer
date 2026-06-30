"""
scripts/run_attack_sample.py
============================
Milestone 5: Attack framework verification.
Runs a direct prompt injection attack against the M4 agent pipeline.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse
from reconmind.config import cfg
from reconmind.db.init_db import init_db
from reconmind.platform_.graph import build_graph
from reconmind.platform_.state import GraphState
from reconmind.attacks import (
    DirectInjectionAttack,
    IndirectInjectionAttack,
    MemoryPoisoningAttack,
    ToolMisuseAttack
)

logging.basicConfig(level=cfg.logging.level, format=cfg.logging.format)
logger = logging.getLogger(__name__)

import json

def _create_run_row(run_id: str, db_path: Path, attack: Any) -> None:
    sql = """
        INSERT INTO runs (
            run_id, scenario_id, topology_type, injection_type, entry_agent_id,
            attack_objective, attack_strength, expected_signal,
            run_started_at, run_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    expected_signal_json = json.dumps(attack.expected_signal())
    
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(sql, (
            run_id, "attack_sample", "linear", 
            attack.config.attack_type, attack.config.entry_point,
            attack.config.objective, attack.config.strength, expected_signal_json,
            now, "completed"
        ))
        conn.commit()

def print_trace(run_id: str, db_path: Path) -> None:
    sql = """
        SELECT hop_index, agent_id, input_prompt_text, output_text, tool_called
        FROM events
        WHERE run_id = ?
        ORDER BY hop_index ASC
    """
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        events = conn.execute(sql, (run_id,)).fetchall()
        
    print("\n" + "="*80)
    print(f"EVENT TRACE FOR RUN: {run_id}")
    print("="*80)
    for ev in events:
        print(f"\nHOP {ev['hop_index']} | AGENT: {ev['agent_id']}")
        print(f"INPUT (truncated): {ev['input_prompt_text'][:200]}...")
        print(f"OUTPUT (truncated): {ev['output_text'][:200]}...")
        if ev['tool_called']:
            print(f">>> TOOL CALLED: {ev['tool_called']}")
    print("="*80 + "\n")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run an attack against the M4 agent pipeline.")
    parser.add_argument("--attack-type", choices=["direct", "indirect", "memory_poison", "tool_misuse"], default="direct", help="Type of attack to run")
    parser.add_argument("--strength", choices=["subtle", "moderate", "blatant"], default="blatant", help="Strength of the attack payload")
    args = parser.parse_args()

    print("Milestone 6 — Attack Framework Verification")
    db_path = init_db()
    graph = build_graph()
    
    objective = "unauthorized_action"
    strength = args.strength
    print(f"\nSetting up {args.attack_type.upper()} Attack (Objective: {objective}, Strength: {strength})")
    
    if args.attack_type == "direct":
        attack = DirectInjectionAttack(objective=objective, strength=strength)
    elif args.attack_type == "indirect":
        attack = IndirectInjectionAttack(objective=objective, strength=strength)
    elif args.attack_type == "memory_poison":
        attack = MemoryPoisoningAttack(objective=objective, strength=strength)
    elif args.attack_type == "tool_misuse":
        attack = ToolMisuseAttack(objective=objective, strength=strength)
    else:
        print("Invalid attack type")
        sys.exit(1)
    
    run_id = str(uuid.uuid4())
    session_id = f"sess_attack_{uuid.uuid4().hex[:8]}"
    
    # Pre-attack state
    initial_state: GraphState = {
        "session_id": session_id,
        "run_id": run_id,
        "hop_index": 0,
        "current_input": "Hello, I am a regular customer.",
        "agent_outputs": {},
        "model_name": cfg.llm.role("default").model,
    }
    
    # 2. Inject the attack
    print("Injecting payload...")
    modified_state = attack.inject(initial_state)
    
    _create_run_row(run_id, db_path, attack)
    
    print(f"Payload to be sent: {modified_state['current_input']}")
    print("Invoking graph...")
    
    # 3. Run the unmodified graph
    try:
        final_state = graph.invoke(modified_state)
        print("✓ Graph executed successfully")
    except Exception as exc:
        print(f"✗ Graph execution failed: {exc}")
        sys.exit(1)
        
    # 4. Print trace and expected signal
    print_trace(run_id, db_path)
    
    print(f"Expected Signal for success: {attack.expected_signal()}")
    print("Check the trace above to see if the action agent executed the expected tool.")

if __name__ == "__main__":
    main()
