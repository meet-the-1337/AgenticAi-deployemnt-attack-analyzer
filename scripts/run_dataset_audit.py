"""
run_dataset_audit.py
====================
Loads CSVs and runs the dataset audit.
"""

import sys
import csv
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from reconmind.analytics.dataset_audit import (
    check_oracle_quality,
    check_sequence_integrity,
    check_feature_variance
)
from reconmind.analytics.audit_report import generate_report

def main():
    data_dir = _REPO_ROOT / "dataset"
    runs_file = data_dir / "dataset_runs.csv"
    events_file = data_dir / "dataset_events.csv"
    
    if not runs_file.exists() or not events_file.exists():
        print("Dataset CSVs not found! Please run the campaign and export first.")
        sys.exit(1)
        
    with runs_file.open("r") as f:
        runs = list(csv.DictReader(f))
        
    with events_file.open("r") as f:
        events = list(csv.DictReader(f))
        
    # Generate and print report
    report = generate_report(runs, events)
    print(report)
    
    # Save machine-readable output for M12
    oracle = check_oracle_quality(runs)
    seq = check_sequence_integrity(runs, events)
    variance = check_feature_variance(runs)
    
    # Identify runs with null outcomes
    null_runs = [r["run_id"] for r in runs if not r.get("injection_outcome")]
    
    drop_runs = set(null_runs + seq["single_event_runs"] + seq["hop_gaps"])
    
    results = {
        "drop_run_ids": list(drop_runs),
        "drop_columns": variance["zero_variance"] + variance["leakage_candidates"],
        "uncertain_run_ids": oracle["uncertain_runs"]
    }
    
    out_path = data_dir / "audit_results.json"
    with out_path.open("w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nSaved machine-readable audit to {out_path.name}")

if __name__ == "__main__":
    main()
