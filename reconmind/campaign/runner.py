"""
reconmind/campaign/runner.py
============================
Orchestrates the campaign execution.
"""

from __future__ import annotations

import logging
import sqlite3
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Set, Tuple

from reconmind.config import cfg
from reconmind.platform_.graph import build_graph
from reconmind.platform_.memory import clear_session_memory
from reconmind.verify.oracle import verify_run
from reconmind.campaign.matrix import RunConfig

from reconmind.attacks import (
    DirectInjectionAttack,
    IndirectInjectionAttack,
    MemoryPoisoningAttack,
    ToolMisuseAttack
)

logger = logging.getLogger(__name__)

def _get_db():
    conn = sqlite3.connect(str(cfg.database.resolved_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# ---------------------------------------------------------------------------
# Resume helpers
# ---------------------------------------------------------------------------
def _get_completed_run_signatures(db_path: str) -> Set[Tuple]:
    """
    Returns a set of (injection_type, objective, strength, defense_config, repeat_index)
    tuples for runs that completed successfully.
    Used by --resume to skip already-done work.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute("""
                SELECT injection_type, attack_objective, attack_strength,
                       defense_config, repeat_index
                FROM runs
                WHERE run_status = 'completed'
                AND scenario_id = 'campaign_run'
            """).fetchall()
        return set(rows)
    except Exception:
        return set()


def _config_signature(config: RunConfig) -> Tuple:
    """Build the matching signature tuple for a RunConfig."""
    return (
        config.attack_type,
        config.objective,
        config.strength,
        config.defense_config,
        config.repeat_index,
    )


# ---------------------------------------------------------------------------
# DB row helpers
# ---------------------------------------------------------------------------
def _create_run_row(run_id: str, session_id: str, config: RunConfig, expected_signal: str) -> None:
    now = datetime.now(tz=timezone.utc).isoformat()
    sql = """
        INSERT INTO runs (
            run_id, scenario_id, topology_type, defense_config,
            injection_type, attack_objective, attack_strength, expected_signal,
            run_started_at, run_status, session_id, repeat_index
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with _get_db() as conn:
        conn.execute(sql, (
            run_id,
            "campaign_run",
            "linear",
            config.defense_config,
            config.attack_type,
            config.objective,
            config.strength,
            expected_signal,
            now,
            "running",
            session_id,
            config.repeat_index,
        ))
        conn.commit()

def _update_run_status(run_id: str, status: str, outcome: str = None) -> None:
    now = datetime.now(tz=timezone.utc).isoformat()
    sql = """
        UPDATE runs 
        SET run_status = ?, run_ended_at = ?, injection_outcome = ?
        WHERE run_id = ?
    """
    with _get_db() as conn:
        conn.execute(sql, (status, now, outcome, run_id))
        conn.commit()


# ---------------------------------------------------------------------------
# Main campaign loop
# ---------------------------------------------------------------------------
def run_campaign(configs: list[RunConfig], dry_run: bool = False, resume: bool = False) -> None:
    if dry_run:
        from reconmind.campaign.matrix import print_matrix_summary
        print_matrix_summary(configs)
        return

    graph = build_graph()
    total = len(configs)

    # Check already completed runs for resume
    completed: Set[Tuple] = set()
    skipped = 0
    if resume:
        completed = _get_completed_run_signatures(str(cfg.database.resolved_path))
        print(f"[resume] Found {len(completed)} already-completed runs in DB")

    for i, config in enumerate(configs, 1):
        # Skip completed runs when resuming
        if resume and _config_signature(config) in completed:
            skipped += 1
            continue

        run_id = str(uuid.uuid4())
        session_id = f"sess_{run_id}"
        
        run_label = f"Run {i}/{total}"
        if skipped:
            run_label += f" (skipped {skipped})"
        print(f"{run_label} [{config.run_type}] | Defense: {config.defense_config} | Attack: {config.attack_type} | Strength: {config.strength}...")
        
        # Override defense config dynamically for this run (bypassing pydantic freeze)
        object.__setattr__(cfg.defense, "active", config.defense_config)
        
        initial_state = {
            "session_id": session_id,
            "run_id": run_id,
            "hop_index": 0,
            "current_input": config.benign_prompt or "Please help me with my account.",
            "agent_outputs": {},
            "model_name": cfg.llm.role("target_agent").model,
        }
        
        try:
            attack_obj = None
            expected_signal = "{}"
            
            if config.run_type == "attack":
                if config.attack_type == "direct_injection":
                    attack_obj = DirectInjectionAttack(objective=config.objective, strength=config.strength)
                elif config.attack_type == "indirect_injection":
                    attack_obj = IndirectInjectionAttack(objective=config.objective, strength=config.strength)
                elif config.attack_type == "memory_poisoning":
                    attack_obj = MemoryPoisoningAttack(objective=config.objective, strength=config.strength)
                elif config.attack_type == "tool_misuse":
                    attack_obj = ToolMisuseAttack(objective=config.objective, strength=config.strength)
                
                if attack_obj:
                    import json
                    expected_signal = json.dumps(attack_obj.expected_signal())
                    initial_state = attack_obj.inject(initial_state)

            _create_run_row(run_id, session_id, config, expected_signal)
            
            # Execute
            graph.invoke(initial_state)
            
            # Verify
            outcome = "clean"
            if config.run_type == "attack":
                outcome = verify_run(run_id)
                
            _update_run_status(run_id, "completed", outcome)
            print(f"  -> Outcome: {outcome}")
            
        except Exception as e:
            logger.error(f"Run {run_id} failed: {e}")
            traceback.print_exc()
            _update_run_status(run_id, "failed")
            print(f"  -> FAILED")
            
        finally:
            clear_session_memory(session_id)
            # Throttle to avoid LLM overload
            time.sleep(2.0)

    print(f"Campaign finished. (Skipped {skipped} already-completed runs)" if skipped else "Campaign finished.")
