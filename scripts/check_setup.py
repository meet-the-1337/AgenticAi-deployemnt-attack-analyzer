"""
scripts/check_setup.py
======================
Milestone 1 acceptance test — run this on every machine to confirm the setup
is correct and both team members see identical output.

What it verifies:
  1. Config loads without error and DB path resolves correctly.
  2. DB is initialized (tables created / already exist — idempotency safe).
  3. Both `runs` and `events` tables exist with the correct column names.
  4. Re-running this script produces the same output (idempotency check).

Usage (from repo root):
    python scripts/check_setup.py

Expected output on success:
    ────────────────────────────────────────────────────────────────
    ✓ Config loaded
      DB path : /absolute/path/to/data/reconmind.db
      LLM     : openai / gpt-4o-mini
      Log level: INFO
    ✓ DB initialised (idempotent — safe to re-run)
    ✓ Table: runs
      cid | name                    | type    | notnull | dflt_value | pk
      ----+-------------------------+---------+---------+------------+----
      0   | run_id                  | TEXT    | 0       | None       | 1
      ...
    ✓ Table: events
      ...
    ────────────────────────────────────────────────────────────────
    ALL CHECKS PASSED — DB ready.
"""

from __future__ import annotations

import sqlite3
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Make sure the repo root is on sys.path when run as a plain script
# (so `from reconmind...` works without `pip install -e .`)
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent          # scripts/
_REPO_ROOT   = _SCRIPT_DIR.parent                      # reconmind/ (repo root)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Imports (after path fix)
# ---------------------------------------------------------------------------
from reconmind.config import cfg
from reconmind.db.init_db import init_db

DIVIDER = "─" * 66


def _print_table_schema(conn: sqlite3.Connection, table_name: str) -> None:
    """Pretty-print PRAGMA table_info output for a given table."""
    rows = conn.execute(f"PRAGMA table_info({table_name});").fetchall()
    if not rows:
        print(f"  ✗ Table '{table_name}' does NOT exist — schema not applied correctly!")
        sys.exit(1)

    col_header = f"  {'cid':<4}  {'name':<30}  {'type':<10}  {'notnull':<7}  {'dflt_value':<12}  {'pk'}"
    print(col_header)
    print("  " + "-" * (len(col_header) - 2))
    for row in rows:
        cid, name, type_, notnull, dflt, pk = row
        print(f"  {cid:<4}  {name:<30}  {type_:<10}  {notnull:<7}  {str(dflt):<12}  {pk}")


def main() -> None:
    print(DIVIDER)

    # ── 1. Config ────────────────────────────────────────────────────────────
    try:
        db_path = cfg.database.resolved_path
        provider = cfg.llm.provider
        model = cfg.llm.openai_model if provider == "openai" else cfg.llm.ollama_model
        print("✓ Config loaded")
        print(f"  DB path  : {db_path}")
        print(f"  LLM      : {provider} / {model}")
        print(f"  Log level: {cfg.logging.level}")
    except Exception as exc:
        print(f"✗ Config load FAILED: {exc}")
        sys.exit(1)

    print()

    # ── 2. DB init (idempotent) ──────────────────────────────────────────────
    try:
        init_db()
        print("✓ DB initialised (idempotent — safe to re-run)")
    except Exception as exc:
        print(f"✗ DB init FAILED: {exc}")
        sys.exit(1)

    print()

    # ── 3. Table schema verification ─────────────────────────────────────────
    expected_tables = {
        "runs": [
            "run_id", "scenario_id", "topology_type", "defense_config",
            "injection_type", "entry_agent_id", "critical_asset_agent_id",
            "total_hops", "hops_to_compromise", "final_outcome",
            "detecting_defense", "run_started_at", "run_ended_at", "run_status",
        ],
        "events": [
            "event_id", "run_id", "hop_index", "agent_id", "agent_role",
            "input_prompt_text", "output_text", "tool_called",
            "tool_result_status", "memory_ops_summary", "model_name",
            "latency_ms", "defense_active", "defense_triggered",
            "injection_present_this_event", "injection_outcome", "timestamp",
        ],
    }

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")

    all_ok = True
    for table_name, expected_cols in expected_tables.items():
        print(f"✓ Table: {table_name}")
        _print_table_schema(conn, table_name)

        # Column name correctness check
        actual_cols = [
            row[1] for row in conn.execute(f"PRAGMA table_info({table_name});")
        ]
        missing = set(expected_cols) - set(actual_cols)
        if missing:
            print(f"\n  ✗ MISSING columns in '{table_name}': {sorted(missing)}")
            all_ok = False
        else:
            print(f"  ✓ All {len(expected_cols)} expected columns present.")
        print()

    conn.close()

    # ── 4. Final verdict ─────────────────────────────────────────────────────
    print(DIVIDER)
    if all_ok:
        print("ALL CHECKS PASSED — DB ready. ✓")
    else:
        print("SOME CHECKS FAILED — review output above. ✗")
        sys.exit(1)
    print(DIVIDER)


if __name__ == "__main__":
    main()
