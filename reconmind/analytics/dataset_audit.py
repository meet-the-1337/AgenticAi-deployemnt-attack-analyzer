"""
reconmind/analytics/dataset_audit.py
====================================
Programmatic checks for dataset quality and class balance.
"""

from collections import defaultdict
import math

def check_class_balance(runs) -> dict:
    total = len(runs)
    if total == 0:
        return {}
        
    attack_runs = [r for r in runs if r.get("injection_type") and r.get("injection_type") != "clean"]
    clean_runs = [r for r in runs if not r.get("injection_type") or r.get("injection_type") == "clean"]
    
    successes = sum(1 for r in attack_runs if r.get("attack_success_binary") == "1" or r.get("attack_success_binary") == 1)
    
    # By attack type
    by_type = defaultdict(lambda: {"total": 0, "success": 0})
    for r in attack_runs:
        typ = r["injection_type"]
        by_type[typ]["total"] += 1
        if r.get("attack_success_binary") in (1, "1"):
            by_type[typ]["success"] += 1
            
    # By strength
    by_strength = defaultdict(lambda: {"total": 0, "success": 0})
    for r in attack_runs:
        st = r.get("attack_strength", "unknown")
        if not st: st = "unknown"
        by_strength[st]["total"] += 1
        if r.get("attack_success_binary") in (1, "1"):
            by_strength[st]["success"] += 1
            
    # By defense
    by_defense = defaultdict(lambda: {"total": 0, "success": 0})
    for r in attack_runs:
        df = r.get("defense_config", "none")
        if not df: df = "none"
        by_defense[df]["total"] += 1
        if r.get("attack_success_binary") in (1, "1"):
            by_defense[df]["success"] += 1

    return {
        "total_runs": total,
        "attack_runs": len(attack_runs),
        "clean_runs": len(clean_runs),
        "overall_success_rate": (successes / len(attack_runs)) if attack_runs else 0,
        "by_type": {k: (v["success"] / v["total"]) if v["total"] > 0 else 0 for k, v in by_type.items()},
        "by_strength": {k: (v["success"] / v["total"]) if v["total"] > 0 else 0 for k, v in by_strength.items()},
        "by_defense": {k: (v["success"] / v["total"]) if v["total"] > 0 else 0 for k, v in by_defense.items()}
    }

def check_feature_variance(runs) -> dict:
    if not runs: return {"zero_variance": [], "leakage_candidates": []}
    
    # Just a simple heuristic for variance (are all values identical?)
    features = list(runs[0].keys())
    zero_var = []
    
    for f in features:
        if f in ["run_id", "session_id", "run_started_at", "run_ended_at"]:
            continue
        vals = set(r.get(f) for r in runs)
        if len(vals) <= 1:
            zero_var.append(f)
            
    # Naive correlation check (biserial proxy) against attack_success_binary
    leakage = []
    # In a full script, use pandas for corr(), but keeping it dependency-light
    return {
        "zero_variance": zero_var,
        "leakage_candidates": leakage
    }

def check_oracle_quality(runs) -> dict:
    null_outcome = 0
    t1, t2, t3 = 0, 0, 0
    uncertain_runs = []
    
    attack_runs = [r for r in runs if r.get("injection_type") and r.get("injection_type") != "clean"]
    
    for r in attack_runs:
        outcome = r.get("injection_outcome")
        if not outcome:
            null_outcome += 1
            
        # Simplified tier tracking - typically derived from confidence or specific outcome tags
        # As placeholder since actual Tier isn't currently outputted to CSV directly yet
        t1 += 1
        
        conf = float(r.get("judge_confidence", 1.0) or 1.0)
        if conf < 0.6:
            uncertain_runs.append(r["run_id"])
            
    return {
        "null_outcomes": null_outcome,
        "tiers": {"T1": t1, "T2": t2, "T3": t3},
        "uncertain_runs": uncertain_runs
    }

def check_sequence_integrity(runs, events) -> dict:
    run_ids = set(r["run_id"] for r in runs)
    
    events_by_run = defaultdict(list)
    for e in events:
        events_by_run[e["run_id"]].append(e)
        
    missing_events = 0
    single_events = []
    hop_gaps = []
    
    for rid in run_ids:
        evs = events_by_run.get(rid, [])
        if not evs:
            missing_events += 1
            continue
            
        if len(evs) == 1:
            single_events.append(rid)
            continue
            
        # Check hop contiguity
        # Sort by timestamp or hop if hop is available
        # Currently we just ensure there are multiple
        pass
        
    return {
        "missing_events": missing_events,
        "single_event_runs": single_events,
        "hop_gaps": hop_gaps
    }
