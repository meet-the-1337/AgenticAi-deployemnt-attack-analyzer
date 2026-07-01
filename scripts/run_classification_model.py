"""
run_classification_model.py
===========================
CLI entry-point for Milestone 13 — multiclass attack-type classification.

Usage
-----
    python scripts/run_classification_model.py                          # defaults
    python scripts/run_classification_model.py --features-from dataset/ # explicit
    python scripts/run_classification_model.py --save-best              # persist best model
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from reconmind.analytics.features import extract_run_features
from reconmind.analytics.classification_model import (
    prepare_classification_data,
    train_classification_models,
    evaluate_classification,
    render_classification_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the ReconMind multiclass attack-type classifier (M13).",
    )
    parser.add_argument(
        "--features-from",
        default=str(_REPO_ROOT / "dataset"),
        help="Directory containing dataset_runs.csv, dataset_events.csv, audit_results.json",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_REPO_ROOT / "models" / "classification"),
        help="Where to save model artefacts, figures, and CSVs",
    )
    parser.add_argument(
        "--save-best",
        action="store_true",
        default=True,
        help="Persist the best model (by macro F1) as a joblib file",
    )
    args = parser.parse_args()

    data_dir = Path(args.features_from)
    out_dir  = Path(args.output_dir)

    # ── load data ──
    runs_file   = data_dir / "dataset_runs.csv"
    events_file = data_dir / "dataset_events.csv"
    audit_file  = data_dir / "audit_results.json"

    if not runs_file.exists() or not events_file.exists():
        print(f"✗ Data not found in {data_dir}.  Run the campaign first.")
        sys.exit(1)

    runs_df   = pd.read_csv(runs_file)
    events_df = pd.read_csv(events_file)

    audit_results: dict = {}
    if audit_file.exists():
        with audit_file.open() as f:
            audit_results = json.load(f)

    # ── feature extraction (shared with M12) ──
    print("Extracting features …")
    features_df = extract_run_features(runs_df, events_df, audit_results)

    # ── data split ──
    print("Preparing classification data …")
    X_train, X_test, y_train, y_test, class_names, le = prepare_classification_data(features_df)

    # Acceptance criterion: all 4 classes must appear in both splits.
    y_test_labels = pd.Series(y_test).map(lambda i: class_names[i])
    print("\n┌─ Split Validation ─────────────────────────────┐")
    print(f"│  Training samples:  {len(y_train):>5}")
    print(f"│  Test samples:      {len(y_test):>5}")
    print("│  Test-set class distribution:")
    for cls, cnt in y_test_labels.value_counts().items():
        print(f"│    {cls:25s} {cnt}")
    print("└────────────────────────────────────────────────┘")

    assert len(set(y_test)) == len(class_names), (
        f"Not all classes in test set!  Got {len(set(y_test))}, expected {len(class_names)}"
    )

    # ── train ──
    print("\nTraining models (Dummy, LR, RF, XGBoost) …")
    models = train_classification_models(X_train, y_train)

    # ── evaluate ──
    print("Evaluating …")
    report = evaluate_classification(models, X_test, y_test, class_names, le)

    figures_dir = out_dir / "figures"
    render_classification_report(report, figures_dir)

    # ── save feature-importance CSV ──
    out_dir.mkdir(parents=True, exist_ok=True)
    imp_path = out_dir / "feature_importances.csv"
    report.feature_importances.to_csv(imp_path)
    print(f"Feature importances → {imp_path}")

    # ── persist best model ──
    if args.save_best:
        real = {k: v for k, v in report.metrics.items() if k != "Dummy Baseline"}
        best_name = max(real, key=lambda k: real[k]["macro_f1"])
        best_f1   = real[best_name]["macro_f1"]
        best_pipe = models[best_name]

        model_path = out_dir / "best_model.joblib"
        joblib.dump({"pipeline": best_pipe, "label_encoder": le, "class_names": class_names}, model_path)

        print(f"\n★ Best model: {best_name}  (Macro F1 = {best_f1:.4f})")
        print(f"  Saved to {model_path}")

    # ── combined results summary (M12 + M13) ──
    m12_model_path = _REPO_ROOT / "models" / "detection" / "best_model.joblib"
    if m12_model_path.exists():
        print("\n" + "=" * 64)
        print("  COMBINED ML RESULTS SUMMARY")
        print("=" * 64)
        print(f"\n  Task 1 — Attack Detection (Binary, M12)")
        print(f"    Best model saved at: {m12_model_path}")
        print(f"\n  Task 2 — Attack Type Classification (4-class, M13)")
        print(f"    Best model: {best_name}")
        print(f"    Macro F1:   {best_f1:.4f}")
        dummy_f1 = report.metrics["Dummy Baseline"]["macro_f1"]
        print(f"    Dummy F1:   {dummy_f1:.4f}  (lift = +{best_f1 - dummy_f1:.4f})")
        print(f"    Classes:    {', '.join(class_names)}")

        # Identify hardest confusion pair from best model's CM
        cm = report.confusion_matrices[best_name]
        np.fill_diagonal(cm, 0)
        i, j = np.unravel_index(cm.argmax(), cm.shape)
        print(f"    Hardest pair: {class_names[i]} ↔ {class_names[j]}  ({cm[i, j]} misclassifications)")
        print("=" * 64)


if __name__ == "__main__":
    main()
