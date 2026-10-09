"""
scripts/run_real_pipeline.py
============================
Milestone 3 acceptance test with real LLM inference.
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

from reconmind.config import cfg
from reconmind.db.init_db import init_db
from reconmind.platform_.graph import build_graph
from reconmind.platform_.nodes import (
    ACTION_AGENT_ID,
    INTAKE_AGENT_ID,
    RETRIEVAL_AGENT_ID,
)
from reconmind.platform_.state import GraphState

logging.basicConfig(level=cfg.logging.level, format=cfg.logging.format)
logger = logging.getLogger(__name__)

DIVIDER = "─" * 80

EXPECTED_AGENTS: list[tuple[str, str]] = [
    (INTAKE_AGENT_ID, "intake"),
    (RETRIEVAL_AGENT_ID, "retrieval"),
    (ACTION_AGENT_ID, "action"),
]


def _create_run_row(run_id: str, db_path: Path) -> None:
    sql = """
        INSERT INTO runs (
            run_id, scenario_id, topology_type,
            run_started_at, run_status
        ) VALUES (?, ?, ?, ?, ?)
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(sql, (run_id, "real_scenario", "linear", now, "running"))
        conn.commit()


def _fetch_events(run_id: str, db_path: Path) -> list[dict[str, Any]]:
    sql = """
        SELECT
            hop_index, agent_id, agent_role, input_prompt_text, output_text,
            latency_ms, temperature, input_tokens, output_tokens, model_name
        FROM events
        WHERE run_id = ?
        ORDER BY hop_index ASC
    """
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, (run_id,)).fetchall()
        return [dict(r) for r in rows]


def main() -> None:
    print(DIVIDER)
    print("Milestone 3 — Real LLM Pipeline Run")

    db_path = init_db()

    run_id = str(uuid.uuid4())
    test_input = "Scan the web application on port 8080 for SQL injection vulnerabilities."

    print(f"run_id : {run_id}")
    print(f"input  : {test_input!r}")
    print(DIVIDER)

    _create_run_row(run_id, db_path)

    try:
        graph = build_graph()
        initial_state: GraphState = {
            "session_id": "test_session",
            "run_id": run_id,
            "hop_index": 0,
            "current_input": test_input,
            "agent_outputs": {},
            "model_name": "qwen3:8b", # from config
        }
        
        print("Invoking graph... This may take a moment depending on your GPU.")
        final_state: GraphState = graph.invoke(initial_state)
        print("✓ Graph invoked successfully")
    except Exception as exc:
        print(f"✗ Graph invocation FAILED: {exc}")
        sys.exit(1)

    print()
    events = _fetch_events(run_id, db_path)
    
    for ev in events:
        print(DIVIDER)
        print(f"Hop {ev['hop_index']} | {ev['agent_id']} ({ev['agent_role']})")
        print(f"Latency: {ev['latency_ms']:.1f}ms | Temp: {ev['temperature']} | Tokens: {ev['input_tokens']} in / {ev['output_tokens']} out | Model: {ev['model_name']}")
        print(f"Input: {ev['input_prompt_text'][:80]}...")
        print(f"Output:\n{ev['output_text']}")
        
    print(DIVIDER)
    print("M3 checks:")
    if len(events) == 3:
        print("✓ 3 rows logged")
    else:
        print(f"✗ Expected 3 rows, got {len(events)}")
        sys.exit(1)
        
    if all(e["input_tokens"] is not None and e["output_tokens"] is not None for e in events):
        print("✓ Token counts present")
    else:
        print("✗ Token counts missing")
        sys.exit(1)

    print("ALL CHECKS PASSED ✓")

if __name__ == "__main__":
    main()
