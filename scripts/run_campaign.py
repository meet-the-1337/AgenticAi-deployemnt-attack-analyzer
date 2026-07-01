"""
run_campaign.py
===============
CLI entrypoint for running the automated campaign matrix.
"""

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Setup venv if available so imports like langgraph work
import subprocess
try:
    pass # In real script we would ensure python is running from venv, assuming it is here based on context
except:
    pass

from reconmind.campaign.matrix import generate_matrix
from reconmind.campaign.runner import run_campaign
from reconmind.campaign.exporter import export_dataset
from reconmind.config import cfg

def main():
    parser = argparse.ArgumentParser(description="Run the ReconMind Campaign Matrix")
    parser.add_argument("--dry-run", action="store_true", help="Print matrix and exit")
    parser.add_argument("--defense", type=str, choices=["none", "heuristic", "judge"], help="Override defense for all runs")
    parser.add_argument("--resume", action="store_true", help="Skip runs already in DB")
    parser.add_argument("--export-only", action="store_true", help="Skip running, just export data")
    
    args = parser.parse_args()
    
    if args.export_only:
        print("Exporting dataset...")
        res = export_dataset(_REPO_ROOT / "dataset")
        print(f"Exported to {res['summary'].parent}")
        return
        
    matrix = generate_matrix()
    
    if args.defense:
        for m in matrix:
            object.__setattr__(m, "defense_config", args.defense)
            
    run_campaign(matrix, dry_run=args.dry_run, resume=args.resume)
    
    if not args.dry_run:
        print("Exporting dataset...")
        export_dataset(_REPO_ROOT / "dataset")

if __name__ == "__main__":
    main()
