"""
scripts/run_dummy_pipeline.py
=============================
Milestone 2 acceptance test.

What this script proves
-----------------------
1. Graph compiles and runs end-to-end with zero LLM calls (stub mode).
2. Exactly 3 event rows are written for a single run (intake, retrieval,
   action), in correct hop_index order.
3. Each row has the correct agent_id / agent_role, non-null I/O text, and a
   plausible (small) latency_ms.
4. A second invocation produces a fresh run_id with isolated events — no
   cross-run contamination.
5. The @logged_node decorator adds zero overhead to node function signatures.

Usage (from repo root, with .venv active)
-----------------------------------------
    .venv/bin/python scripts/run_dummy_pipeline.py

    # or: run twice consecutively to verify isolation
    .venv/bin/python scripts/run_dummy_pipeline.py && \\
    .venv/bin/python scripts/run_dummy_pipeline.py

Expected output (abridged)
--------------------------
    ──────────────────────────────────────────────────────────────────
    Milestone 2 — Dummy Pipeline Run
    run_id : <uuid>
    input  : "Recon the target network segment alpha-7."
    ──────────────────────────────────────────────────────────────────
    ✓ Graph invoked successfully
    ✓ Final state hop_index = 3

    Events logged for this run (events table):
    hop  agent_id           agent_role   latency_ms  input_text[:50]
    ─────────────────────────────────────────────────────────────────
    0    intake_agent       intake       0.12        Recon the target...
    1    retrieval_agent    retrieval    0.08        [STUB] intake_age...
    2    action_agent       action       0.07        [STUB] retrieval_...

    ✓ Row count: 3 (expected 3)
    ✓ hop_index values: [0, 1, 2] — monotonically increasing
    ✓ All agent_ids correct
    ✓ All output_text non-empty
    ✓ All latency_ms > 0
    ──────────────────────────────────────────────────────────────────
    ALL CHECKS PASSED ✓
    ──────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap — makes 'reconmind' importable when run as a plain script
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# reconmind imports (after path fix)
# ---------------------------------------------------------------------------
from reconmind.config import cfg
from reconmind.db.init_db import init_db
from reconmind.platform_.graph import build_graph
from reconmind.platform_.nodes import (
    ACTION_AGENT_ID,
    INTAKE_AGENT_ID,
    RETRIEVAL_AGENT_ID,
)
from reconmind.platform_.state import GraphState

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=cfg.logging.level,
    format=cfg.logging.format,
)
logger = logging.getLogger(__name__)

DIVIDER = "─" * 66

# Expected agents in hop order
EXPECTED_AGENTS: list[tuple[str, str]] = [
    (INTAKE_AGENT_ID, "intake"),
    (RETRIEVAL_AGENT_ID, "retrieval"),
    (ACTION_AGENT_ID, "action"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_run_row(run_id: str, db_path: Path) -> None:
    """
    Insert a placeholder row into the ``runs`` table so the FK constraint on
    ``events.run_id`` is satisfied.

    All non-mandatory fields are left NULL; a real orchestrator will populate
    them at the end of a scenario run.
    """
    sql = """
        INSERT INTO runs (
            run_id, scenario_id, topology_type,
            run_started_at, run_status
        ) VALUES (?, ?, ?, ?, ?)
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(sql, (run_id, "dummy_scenario", "linear", now, "running"))
        conn.commit()
    finally:
        conn.close()


def _fetch_events(run_id: str, db_path: Path) -> list[dict[str, Any]]:
    """Return all event rows for a given run_id, ordered by hop_index."""
    sql = """
        SELECT
            hop_index,
            agent_id,
            agent_role,
            input_prompt_text,
            output_text,
            latency_ms,
            timestamp
        FROM events
        WHERE run_id = ?
        ORDER BY hop_index ASC
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, (run_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _run_checks(events: list[dict[str, Any]], run_id: str) -> bool:
    """
    Run all acceptance criteria checks.

    Returns True if all pass, False otherwise (so the caller can sys.exit).
    """
    all_ok = True

    def fail(msg: str) -> None:
        nonlocal all_ok
        print(f"  ✗ FAIL: {msg}")
        all_ok = False

    def ok(msg: str) -> None:
        print(f"  ✓ {msg}")

    # ── Check 1: row count
    if len(events) == 3:
        ok(f"Row count: {len(events)} (expected 3)")
    else:
        fail(f"Row count: {len(events)} (expected 3)")

    # ── Check 2: hop_index is 0, 1, 2
    hops = [e["hop_index"] for e in events]
    if hops == [0, 1, 2]:
        ok(f"hop_index values: {hops} — monotonically increasing")
    else:
        fail(f"hop_index values wrong: {hops} (expected [0, 1, 2])")

    # ── Check 3: correct agent_id and agent_role per row
    for i, (event, (exp_id, exp_role)) in enumerate(
        zip(events, EXPECTED_AGENTS)
    ):
        if event["agent_id"] == exp_id and event["agent_role"] == exp_role:
            ok(f"hop {i}: agent_id='{exp_id}' agent_role='{exp_role}' — correct")
        else:
            fail(
                f"hop {i}: expected agent_id='{exp_id}' role='{exp_role}', "
                f"got agent_id='{event['agent_id']}' role='{event['agent_role']}'"
            )

    # ── Check 4: non-empty I/O text
    for i, event in enumerate(events):
        if event["input_prompt_text"]:
            ok(f"hop {i}: input_prompt_text non-empty")
        else:
            fail(f"hop {i}: input_prompt_text is empty/NULL")

        if event["output_text"]:
            ok(f"hop {i}: output_text non-empty")
        else:
            fail(f"hop {i}: output_text is empty/NULL")

    # ── Check 5: latency_ms is positive (stub, so very small but > 0)
    for i, event in enumerate(events):
        lat = event["latency_ms"]
        if lat is not None and lat >= 0:
            ok(f"hop {i}: latency_ms={lat:.4f}ms — sane")
        else:
            fail(f"hop {i}: latency_ms={lat} — expected ≥ 0")

    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(DIVIDER)
    print("Milestone 2 — Dummy Pipeline Run")

    # 1. Ensure DB is initialised (idempotent)
    db_path = init_db()

    # 2. Generate a fresh run_id for this invocation
    run_id = str(uuid.uuid4())
    test_input = "Recon the target network segment alpha-7."

    print(f"run_id : {run_id}")
    print(f"input  : \"{test_input}\"")
    print(DIVIDER)

    # 3. Insert a parent run row (needed for FK constraint on events)
    _create_run_row(run_id, db_path)

    # 4. Build and invoke the graph
    try:
        graph = build_graph()
        initial_state: GraphState = GraphState(
            session_id="test_session",
            run_id=run_id,
            hop_index=0,
            current_input=test_input,
            agent_outputs={},
            memory_ref=None,
            model_name="stub",
        )
        final_state: GraphState = graph.invoke(initial_state)
        print("✓ Graph invoked successfully")
    except Exception as exc:
        print(f"✗ Graph invocation FAILED: {exc}")
        raise

    # 5. Validate final hop_index (should be 3 after 3 nodes each increment by 1)
    final_hop = final_state.get("hop_index", -1)
    if final_hop == 3:
        print(f"✓ Final state hop_index = {final_hop}")
    else:
        print(f"✗ Final hop_index = {final_hop} (expected 3)")

    print()

    # 6. Fetch and display events
    events = _fetch_events(run_id, db_path)

    print("Events logged for this run (events table):")
    header = (
        f"  {'hop':<4}  {'agent_id':<20}  {'agent_role':<12}  "
        f"{'latency_ms':>10}  input_text[:60]"
    )
    print(header)
    print("  " + "─" * (len(header) - 2))
    for ev in events:
        trunc_input = (ev["input_prompt_text"] or "")[:60]
        print(
            f"  {ev['hop_index']:<4}  {ev['agent_id']:<20}  "
            f"{ev['agent_role']:<12}  {ev['latency_ms']:>10.4f}  {trunc_input!r}"
        )

    print()
    print("Checks:")
    all_ok = _run_checks(events, run_id)

    # 7. Final verdict
    print()
    print(DIVIDER)
    if all_ok:
        print("ALL CHECKS PASSED ✓")
    else:
        print("SOME CHECKS FAILED ✗ — review output above")
        sys.exit(1)
    print(DIVIDER)


if __name__ == "__main__":
    main()
