"""
run_detection_model.py
======================
Runs the binary classification attack detection pipeline.
"""

import sys
import argparse
import pandas as pd
import json
import joblib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from reconmind.analytics.features import extract_run_features
from reconmind.analytics.detection_model import prepare_data, train_baseline, evaluate_models
from reconmind.analytics.evaluation import render_report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features-from", default=str(_REPO_ROOT / "dataset"))
    parser.add_argument("--output-dir", default=str(_REPO_ROOT / "models" / "detection"))
    parser.add_argument("--save-best", action="store_true", default=True)
    args = parser.parse_args()
    
    data_dir = Path(args.features_from)
    out_dir = Path(args.output_dir)
    
    runs_file = data_dir / "dataset_runs.csv"
    events_file = data_dir / "dataset_events.csv"
    audit_file = data_dir / "audit_results.json"
    
    if not runs_file.exists() or not events_file.exists():
        print(f"Data not found in {data_dir}. Run campaign first.")
        sys.exit(1)
        
    runs_df = pd.read_csv(runs_file)
    events_df = pd.read_csv(events_file)
    
    audit_results = {}
    if audit_file.exists():
        with audit_file.open("r") as f:
            audit_results = json.load(f)
            
    print("Extracting features...")
    features_df = extract_run_features(runs_df, events_df, audit_results)
    
    print("Preparing data (stratified split)...")
    X_train, X_test, y_train, y_test = prepare_data(features_df)
    
    # Very small datasets might raise issues with class balancing if classes are 0.
    if len(y_train.unique()) < 2:
        print("Error: Target variable y_train has only 1 class. Campaign likely didn't run properly.")
        sys.exit(1)
        
    print("Training baseline models (LR, RF, XGB)...")
    models = train_baseline(X_train, y_train)
    
    print("Evaluating...")
    report = evaluate_models(models, X_test, y_test)
    
    render_report(report, out_dir / "figures")
    
    if args.save_best:
        # Find best model by F1 Score
        best_name = max(report.metrics.items(), key=lambda x: x[1]['f1'])[0]
        best_model = models[best_name]
        
        print(f"\nBest model: {best_name} (F1 = {report.metrics[best_name]['f1']:.4f})")
        out_dir.mkdir(parents=True, exist_ok=True)
        model_path = out_dir / "best_model.joblib"
        joblib.dump(best_model, model_path)
        print(f"Saved to {model_path}")

if __name__ == "__main__":
    main()
