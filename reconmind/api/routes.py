import sqlite3
import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from reconmind.config import cfg
from reconmind.platform_.graph import build_graph
from reconmind.verify.oracle import verify_run
from reconmind.attacks.direct_injection import DirectInjectionAttack
from reconmind.attacks.indirect_injection import IndirectInjectionAttack
from reconmind.attacks.memory_poisoning import MemoryPoisoningAttack
from reconmind.attacks.tool_misuse import ToolMisuseAttack

router = APIRouter()

class RunLiveRequest(BaseModel):
    prompt: str
    mode: str  # "benign" | "attack"
    attack_type: Optional[str] = None
    strength: Optional[str] = "blatant"

def get_db():
    conn = sqlite3.connect(str(cfg.database.resolved_path))
    conn.row_factory = sqlite3.Row
    return conn

def _create_run_row(run_id: str, mode: str, attack: Any = None):
    now = datetime.now(tz=timezone.utc).isoformat()
    injection_type = attack.config.attack_type if attack else None
    entry_point = attack.config.entry_point if attack else None
    attack_objective = attack.config.objective if attack else None
    attack_strength = attack.config.strength if attack else None
    expected_signal = json.dumps(attack.expected_signal()) if attack else None
    
    sql = """
        INSERT INTO runs (
            run_id, scenario_id, topology_type, injection_type, entry_agent_id,
            attack_objective, attack_strength, expected_signal,
            run_started_at, run_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with get_db() as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(sql, (
            run_id, "live_demo", "linear", injection_type, entry_point,
            attack_objective, attack_strength, expected_signal, now, "completed"
        ))
        conn.commit()

@router.post("/run/live")
def run_live(req: RunLiveRequest):
    run_id = str(uuid.uuid4())
    graph = build_graph()
    
    initial_state = {
        "current_input": req.prompt,
        "session_id": f"live_{run_id}",
        "run_id": run_id
    }
    
    attack_obj = None
    if req.mode == "attack":
        if req.attack_type == "direct_prompt_injection":
            attack_obj = DirectInjectionAttack(objective="unauthorized_action", strength=req.strength)
        elif req.attack_type == "indirect_prompt_injection":
            attack_obj = IndirectInjectionAttack(objective="unauthorized_action", strength=req.strength)
        elif req.attack_type == "memory_poisoning":
            attack_obj = MemoryPoisoningAttack(objective="unauthorized_action", strength=req.strength)
        elif req.attack_type == "tool_misuse":
            attack_obj = ToolMisuseAttack(objective="unauthorized_action", strength=req.strength)
        else:
            attack_obj = DirectInjectionAttack(objective="unauthorized_action", strength="blatant")
            
        _create_run_row(run_id, req.mode, attack_obj)
        modified_state = attack_obj.inject(initial_state)
        modified_state["run_id"] = run_id
        final_state = graph.invoke(modified_state)
        outcome = verify_run(run_id)
    else:
        _create_run_row(run_id, req.mode)
        final_state = graph.invoke(initial_state)
        outcome = "clean"
        
    with get_db() as conn:
        events = [dict(r) for r in conn.execute("SELECT * FROM events WHERE run_id = ? ORDER BY hop_index ASC", (run_id,)).fetchall()]
        
    return {
        "run_id": run_id,
        "outcome": outcome,
        "events": events
    }

@router.get("/runs")
def get_runs():
    with get_db() as conn:
        runs = [dict(r) for r in conn.execute("SELECT run_id, scenario_id, injection_type, attack_strength, injection_outcome, run_started_at FROM runs ORDER BY run_started_at DESC").fetchall()]
    return {"runs": runs}

@router.get("/runs/{run_id}/events")
def get_run_events(run_id: str):
    with get_db() as conn:
        events = [dict(r) for r in conn.execute("SELECT * FROM events WHERE run_id = ? ORDER BY hop_index ASC", (run_id,)).fetchall()]
        row = conn.execute("SELECT injection_outcome FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not events:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"events": events, "outcome": row["injection_outcome"] if row else "unknown"}
