"""
Export all SQLite data to static JSON files for serverless deployment.
These files go into frontend/public/api/ so they can be fetched like real API responses.
"""
import sqlite3
import json
import os

DB_PATH = "data/reconmind.db"
OUT_DIR = "frontend/public/api"

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(f"{OUT_DIR}/runs", exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 1. /runs — all runs (for KPIs)
rows = conn.execute("""
    SELECT run_id, scenario_id, injection_type, attack_strength, 
           injection_outcome, run_started_at
    FROM runs ORDER BY run_started_at DESC
""").fetchall()
all_runs = [dict(r) for r in rows]
with open(f"{OUT_DIR}/runs.json", "w") as f:
    json.dump({"runs": all_runs}, f)
print(f"✅ Exported {len(all_runs)} runs to runs.json")

# 2. /runs/enriched — top 15 with events + prompt
enriched = []
top_runs = conn.execute("""
    SELECT run_id, injection_type, attack_strength, injection_outcome,
           attack_objective, topology_type, total_hops, hops_to_compromise,
           run_started_at, defense_config, entry_agent_id
    FROM runs ORDER BY run_started_at DESC LIMIT 15
""").fetchall()
for run in top_runs:
    rd = dict(run)
    events = conn.execute("""
        SELECT agent_role, input_prompt_text, output_text, tool_called,
               defense_triggered, defense_active, injection_present_this_event,
               defense_confidence_score, latency_ms, input_tokens, output_tokens,
               hop_index, memory_ops_summary
        FROM events WHERE run_id = ? ORDER BY hop_index ASC
    """, (rd["run_id"],)).fetchall()
    rd["events"] = [dict(e) for e in events]
    rd["prompt"] = rd["events"][0].get("input_prompt_text", "") if rd["events"] else ""
    enriched.append(rd)
with open(f"{OUT_DIR}/runs_enriched.json", "w") as f:
    json.dump({"runs": enriched}, f)
print(f"✅ Exported {len(enriched)} enriched runs")

# 3. /analytics/vulnerability-summary
vuln_rows = conn.execute("""
    SELECT e.agent_role,
           COUNT(DISTINCT e.run_id) as total_targeted,
           COUNT(DISTINCT CASE WHEN r.injection_outcome = 'full_success' THEN e.run_id END) as total_compromised
    FROM events e JOIN runs r ON e.run_id = r.run_id
    WHERE r.injection_type IS NOT NULL
    GROUP BY e.agent_role
""").fetchall()
vuln = {}
for r in vuln_rows:
    d = dict(r)
    vuln[d["agent_role"]] = {"total_targeted": d["total_targeted"], "total_compromised": d["total_compromised"]}
with open(f"{OUT_DIR}/vulnerability_summary.json", "w") as f:
    json.dump({"vulnerability": vuln}, f)
print(f"✅ Exported vulnerability summary ({len(vuln)} agents)")

# 4. /runs/{run_id}/events — individual run event files
all_run_ids = [r["run_id"] for r in all_runs]
for rid in all_run_ids:
    events = conn.execute("SELECT * FROM events WHERE run_id = ? ORDER BY hop_index ASC", (rid,)).fetchall()
    outcome_row = conn.execute("SELECT injection_outcome FROM runs WHERE run_id = ?", (rid,)).fetchone()
    data = {"events": [dict(e) for e in events], "outcome": outcome_row["injection_outcome"] if outcome_row else "unknown"}
    with open(f"{OUT_DIR}/runs/{rid}.json", "w") as f:
        json.dump(data, f)
print(f"✅ Exported event files for {len(all_run_ids)} runs")

# 5. /analytics/injection-scores
scores = conn.execute("""
    SELECT r.run_id, r.injection_type, r.attack_strength,
           r.injection_outcome, r.attack_objective,
           MAX(e.tool_called) as tool_called, r.run_started_at
    FROM runs r LEFT JOIN events e ON e.run_id = r.run_id
    WHERE r.injection_type IS NOT NULL
    GROUP BY r.run_id ORDER BY r.run_started_at DESC
""").fetchall()
with open(f"{OUT_DIR}/injection_scores.json", "w") as f:
    json.dump({"data": [dict(r) for r in scores]}, f)
print(f"✅ Exported {len(scores)} injection scores")

# 6. /analytics/defense-comparison
defense = conn.execute("""
    SELECT r.injection_type, e.defense_active,
           COUNT(*) as total,
           SUM(CASE WHEN e.defense_triggered=1 THEN 1 ELSE 0 END) as triggered,
           AVG(e.latency_ms) as avg_latency
    FROM events e JOIN runs r ON e.run_id = r.run_id
    WHERE e.defense_active IS NOT NULL
    GROUP BY r.injection_type, e.defense_active
""").fetchall()
with open(f"{OUT_DIR}/defense_comparison.json", "w") as f:
    json.dump({"data": [dict(r) for r in defense]}, f)
print(f"✅ Exported defense comparison")

# 7. /analytics/vulnerability (per-agent per-attack-type)
vuln_detail = conn.execute("""
    SELECT e.agent_role, r.injection_type,
           COUNT(*) as total,
           SUM(CASE WHEN r.injection_outcome='full_success' THEN 1 ELSE 0 END) as successes
    FROM events e JOIN runs r ON e.run_id = r.run_id
    WHERE r.injection_type IS NOT NULL
    GROUP BY e.agent_role, r.injection_type
""").fetchall()
with open(f"{OUT_DIR}/vulnerability.json", "w") as f:
    json.dump({"data": [dict(r) for r in vuln_detail]}, f)
print(f"✅ Exported detailed vulnerability data")

conn.close()
print("\n🎉 All data exported to frontend/public/api/")
print("   Frontend can now run without the Python backend!")
