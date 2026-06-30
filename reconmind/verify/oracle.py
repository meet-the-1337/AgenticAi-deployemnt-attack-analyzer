"""
reconmind.verify.oracle
=======================
Main entry point for verification.
"""

import json
import logging
import sqlite3
from typing import Optional

from reconmind.config import cfg
from reconmind.verify.tool_check import check_tool_signal
from reconmind.verify.memory_check import check_memory_signal
from reconmind.verify.judge_check import check_with_judge

logger = logging.getLogger(__name__)

def verify_run(run_id: str) -> str:
    db_path = str(cfg.database.resolved_path)
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        run_row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        
        if not run_row:
            logger.error(f"Run {run_id} not found.")
            return "error"
            
        expected_signal_raw = run_row["expected_signal"]
        if not expected_signal_raw:
            logger.warning(f"No expected_signal for run {run_id}. Cannot verify.")
            return "error"
            
        expected_signal = json.loads(expected_signal_raw)
        injection_type = run_row["injection_type"]
        
        events = [dict(r) for r in conn.execute("SELECT * FROM events WHERE run_id = ? ORDER BY hop_index ASC", (run_id,)).fetchall()]
        
        # Tier 1: Tool check
        result = check_tool_signal(events, expected_signal)
        tier_used = "Tier 1 (Tool)"
        confidence = None
        
        # Tier 2: Memory check (for memory_poisoning specifically)
        if not result and injection_type == "memory_poisoning":
            session_id = events[0]["run_id"] if events else run_id # our scripts set session_id to related or run_id? Wait, session_id is not in events.
            # We can grab session_id from session_memory by run_id but session_memory links to session_id. 
            # In our mock runs we made session_id = run_id or sess_attack_..., we don't store session_id in runs!
            # Let's just pass db_path to memory check to query session_memory by timestamp maybe? 
            # Or just check events for memory_ops_summary matching the expected signal.
            result = check_memory_signal(events, expected_signal)
            tier_used = "Tier 2 (Memory)"
            
        # Tier 3: LLM Judge fallback
        if not result:
            result_obj = check_with_judge(events, expected_signal, run_row)
            result = result_obj["outcome"]
            confidence = result_obj["confidence"]
            tier_used = "Tier 3 (Judge)"
            
        # Update runs table
        sql = "UPDATE runs SET injection_outcome = ?, judge_confidence = ? WHERE run_id = ?"
        conn.execute(sql, (result, confidence, run_id))
        conn.commit()
        
        logger.info(f"Run {run_id} verified as {result} by {tier_used}")
        return result
