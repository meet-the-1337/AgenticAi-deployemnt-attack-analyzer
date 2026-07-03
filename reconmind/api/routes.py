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

def _create_run_row(run_id: str, session_id: str, mode: str, attack: Any = None):
    now = datetime.now(tz=timezone.utc).isoformat()
    injection_type = attack.config.attack_type if attack else None
    entry_point = attack.config.entry_point if attack else None
    attack_objective = attack.config.objective if attack else None
    attack_strength = attack.config.strength if attack else None
    expected_signal = json.dumps(attack.expected_signal()) if attack else None
    
    sql = """
        INSERT INTO runs (
            run_id, scenario_id, session_id, topology_type, injection_type, entry_agent_id,
            attack_objective, attack_strength, expected_signal,
            run_started_at, run_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with get_db() as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(sql, (
            run_id, "live_demo", session_id, "linear", injection_type, entry_point,
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
            
        _create_run_row(run_id, initial_state["session_id"], req.mode, attack_obj)
        modified_state = attack_obj.inject(initial_state)
        modified_state["run_id"] = run_id
        final_state = graph.invoke(modified_state)
        outcome = verify_run(run_id)
    else:
        _create_run_row(run_id, initial_state["session_id"], req.mode)
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
def get_runs(
    attack_type: Optional[str] = None,
    outcome: Optional[str] = None,
    defense: Optional[str] = None,
    strength: Optional[str] = None
):
    sql = "SELECT run_id, scenario_id, injection_type, attack_strength, injection_outcome, run_started_at FROM runs WHERE 1=1"
    params = []
    
    if attack_type:
        sql += " AND injection_type = ?"
        params.append(attack_type)
    if outcome:
        sql += " AND injection_outcome = ?"
        params.append(outcome)
    if strength:
        sql += " AND attack_strength = ?"
        params.append(strength)
    # Defense filtering would require parsing scenario_id or joining events, simplify for now
    
    sql += " ORDER BY run_started_at DESC"
    
    with get_db() as conn:
        runs = [dict(r) for r in conn.execute(sql, params).fetchall()]
    return {"runs": runs}

@router.get("/runs/{run_id}/events")
def get_run_events(run_id: str):
    with get_db() as conn:
        events = [dict(r) for r in conn.execute("SELECT * FROM events WHERE run_id = ? ORDER BY hop_index ASC", (run_id,)).fetchall()]
        row = conn.execute("SELECT injection_outcome FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not events:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"events": events, "outcome": row["injection_outcome"] if row else "unknown"}

@router.get("/analytics/vulnerability")
def get_vulnerability():
    """Per-agent compromise breakdown for VulnerabilityReport page."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT 
                e.agent_role,
                r.injection_type,
                COUNT(*) as total,
                SUM(CASE WHEN r.injection_outcome='full_success' THEN 1 ELSE 0 END) as successes
            FROM events e
            JOIN runs r ON e.run_id = r.run_id
            WHERE r.injection_type IS NOT NULL
            GROUP BY e.agent_role, r.injection_type
        """).fetchall()
    return {"data": [dict(r) for r in rows]}

@router.get("/analytics/injection-scores")
def get_injection_scores():
    """Scored runs for InjectionScorer page."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT 
                r.run_id, r.injection_type, r.attack_strength,
                r.injection_outcome, r.attack_objective,
                MAX(e.tool_called) as tool_called,
                r.run_started_at
            FROM runs r
            LEFT JOIN events e ON e.run_id = r.run_id
            WHERE r.injection_type IS NOT NULL
            GROUP BY r.run_id
            ORDER BY r.run_started_at DESC
        """).fetchall()
    return {"data": [dict(r) for r in rows]}

@router.get("/analytics/defense-comparison")
def get_defense_comparison():
    """Heuristic vs judge detection rates for DefenseComparison page."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT 
                r.injection_type,
                e.defense_active,
                COUNT(*) as total,
                SUM(CASE WHEN e.defense_triggered=1 THEN 1 ELSE 0 END) as triggered,
                AVG(e.latency_ms) as avg_latency
            FROM events e
            JOIN runs r ON e.run_id = r.run_id
            WHERE e.defense_active IS NOT NULL
            GROUP BY r.injection_type, e.defense_active
        """).fetchall()
    return {"data": [dict(r) for r in rows]}

@router.get("/analytics/attack-trends")
def get_attack_trends():
    """Success rate over time for Dashboard trend chart."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT 
                DATE(run_started_at) as date,
                injection_type,
                COUNT(*) as total,
                SUM(CASE WHEN injection_outcome='full_success' THEN 1 ELSE 0 END) as successes
            FROM runs
            WHERE injection_type IS NOT NULL
            GROUP BY DATE(run_started_at), injection_type
            ORDER BY date ASC
        """).fetchall()
    return {"data": [dict(r) for r in rows]}

@router.get("/runs/export")
def export_runs():
    """CSV export of all runs."""
    import csv, io
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY run_started_at DESC").fetchall()
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows([dict(r) for r in rows])
    from fastapi.responses import Response
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reconmind_runs.csv"}
    )

@router.get("/analytics/vulnerability-summary")
def get_vulnerability_summary():
    """Aggregated per-agent compromise stats for Dashboard card chart."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT 
                e.agent_role,
                COUNT(DISTINCT e.run_id) as total_targeted,
                COUNT(DISTINCT CASE WHEN r.injection_outcome = 'full_success' THEN e.run_id END) as total_compromised
            FROM events e
            JOIN runs r ON e.run_id = r.run_id
            WHERE r.injection_type IS NOT NULL
            GROUP BY e.agent_role
        """).fetchall()
    result = {}
    for r in rows:
        role = dict(r)
        key = role["agent_role"]
        result[key] = {
            "total_targeted": role["total_targeted"],
            "total_compromised": role["total_compromised"],
        }
    return {"vulnerability": result}

@router.get("/runs/enriched")
def get_enriched_runs(limit: int = 15):
    """Full run details with prompt text and event summary for incident queue."""
    with get_db() as conn:
        runs = conn.execute("""
            SELECT 
                r.run_id, r.injection_type, r.attack_strength,
                r.injection_outcome, r.attack_objective, r.topology_type,
                r.total_hops, r.hops_to_compromise, r.run_started_at,
                r.defense_config, r.entry_agent_id
            FROM runs r
            ORDER BY r.run_started_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        
        enriched = []
        for run in runs:
            rd = dict(run)
            events = conn.execute("""
                SELECT agent_role, input_prompt_text, output_text,
                       tool_called, defense_triggered, defense_active,
                       injection_present_this_event, defense_confidence_score,
                       latency_ms, input_tokens, output_tokens, hop_index,
                       memory_ops_summary
                FROM events 
                WHERE run_id = ? 
                ORDER BY hop_index ASC
            """, (rd["run_id"],)).fetchall()
            rd["events"] = [dict(e) for e in events]
            # Extract the original user prompt from the first event
            if rd["events"]:
                rd["prompt"] = rd["events"][0].get("input_prompt_text", "")
            else:
                rd["prompt"] = ""
            enriched.append(rd)
        
    return {"runs": enriched}

