"""
scripts/run_verification_sample.py
==================================
Runs all attack-sample traces generated so far through verify_run()
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from reconmind.config import cfg
from reconmind.verify.oracle import verify_run

logging.basicConfig(level=cfg.logging.level, format=cfg.logging.format)

def main() -> None:
    print("Milestone 7 — Ground Truth Verification Oracle")
    db_path = str(cfg.database.resolved_path)
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        runs = conn.execute("SELECT run_id, injection_type, attack_strength, attack_objective FROM runs WHERE scenario_id = 'attack_sample'").fetchall()
        
    if not runs:
        print("No attack samples found in DB. Run scripts/run_attack_sample.py first.")
        sys.exit(0)
        
    print(f"Found {len(runs)} attack runs to verify.\n")
    print(f"{'RUN_ID':<15} | {'ATTACK_TYPE':<25} | {'STRENGTH':<10} | {'OUTCOME':<15}")
    print("-" * 75)
    
    for r in runs:
        run_id = r["run_id"]
        outcome = verify_run(run_id)
        
        # Reload to get the tier/confidence for display
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT injection_outcome, judge_confidence FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        
        strength_str = r['attack_strength'] or "N/A"
        outcome_str = row['injection_outcome'] or "N/A"
            
        print(f"{run_id[:13]}.. | {r['injection_type']:<25} | {strength_str:<10} | {outcome_str:<15}")
        
if __name__ == "__main__":
    main()
