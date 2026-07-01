"""
reconmind/analytics/audit_report.py
===================================
Produces human-readable summary of the dataset audit.
"""

from .dataset_audit import (
    check_class_balance,
    check_feature_variance,
    check_oracle_quality,
    check_sequence_integrity
)

def generate_report(runs, events) -> str:
    balance = check_class_balance(runs)
    variance = check_feature_variance(runs)
    oracle = check_oracle_quality(runs)
    seq = check_sequence_integrity(runs, events)
    
    if not balance:
        return "Dataset is empty. Run campaign first."
        
    sr = balance['overall_success_rate'] * 100
    pass_balance = "[PASS]" if 25 <= sr <= 70 else "[FAIL]"
    
    # Format the report string
    report = []
    report.append("=== ReconMind Dataset Audit ===")
    report.append(f"Total runs: {balance['total_runs']}")
    report.append(f"  Attack runs: {balance['attack_runs']}  |  Clean runs: {balance['clean_runs']}\n")
    
    report.append("CLASS BALANCE")
    report.append(f"  attack_success_binary: {sr:.1f}%  ← TARGET: 25-70% {pass_balance}")
    report.append("  By attack type:")
    for typ, r in balance['by_type'].items():
        report.append(f"    {typ}: {r*100:.0f}% success")
        
    report.append("  By strength (should increase):")
    st_str = "  ".join([f"{k}: {v*100:.0f}%" for k, v in balance['by_strength'].items()])
    report.append(f"    {st_str}")
    
    report.append("  By defense (should decrease):")
    df_str = "  ".join([f"{k}: {v*100:.0f}%" for k, v in balance['by_defense'].items()])
    report.append(f"    {df_str}\n")
    
    report.append("ORACLE QUALITY")
    report.append(f"  NULL injection_outcome: {oracle['null_outcomes']} runs")
    report.append(f"  Tier resolution: T1={oracle['tiers']['T1']}  T2={oracle['tiers']['T2']}  T3={oracle['tiers']['T3']}")
    report.append(f"  Low-confidence judge labels (<0.6): {len(oracle['uncertain_runs'])} runs\n")
    
    report.append("FEATURE VARIANCE")
    report.append(f"  Zero-variance columns: {variance['zero_variance']}")
    report.append(f"  Potential leakage (corr > 0.9 with label): {variance['leakage_candidates']}\n")
    
    report.append("SEQUENCE INTEGRITY")
    report.append(f"  Runs with missing events: {seq['missing_events']}")
    report.append(f"  Runs with hop gaps: {len(seq['hop_gaps'])}")
    report.append(f"  Single-event runs: {len(seq['single_event_runs'])}")
    
    return "\n".join(report)
