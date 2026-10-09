"""
scripts/merge_datasets.py
=========================
Merges ReconMind's existing synthetic dataset with AgentDojo-extracted data.

Usage (from repo root with .venv active):
  .venv/bin/python scripts/merge_datasets.py

  # Custom paths:
  .venv/bin/python scripts/merge_datasets.py \\
    --existing-runs   dataset/dataset_runs.csv \\
    --existing-events dataset/dataset_events.csv \\
    --new-runs        dataset/agentdojo_runs.csv \\
    --new-events      dataset/agentdojo_events.csv \\
    --out-dir         dataset/merged

Output:
  dataset/merged/dataset_runs.csv    ← drop-in replacement for training
  dataset/merged/dataset_events.csv  ← drop-in replacement for training
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# Columns that MUST exist in the runs CSV for deep_model.py to work
REQUIRED_RUN_COLS = [
    "run_id",
    "injection_type",
    "injection_outcome",
    "attack_success_binary",
]

# Columns that MUST exist in the events CSV for deep_model.py to work
REQUIRED_EVENT_COLS = [
    "run_id",
    "hop_index",
    "agent_role",
    "input_prompt_text",
    "output_text",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "defense_triggered",
    "defense_active",
    "defense_confidence_score",
    "tool_called",
]


def _validate_csv(path: Path, required_cols: list[str], label: str) -> pd.DataFrame:
    """Load and validate a CSV, return DataFrame."""
    if not path.exists():
        raise FileNotFoundError(f"{label} file not found: {path}")
    df = pd.read_csv(path)
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")
    logger.info(f"Loaded {label}: {len(df)} rows, {len(df.columns)} columns — {path}")
    return df


def _align_columns(df: pd.DataFrame, required_cols: list[str]) -> pd.DataFrame:
    """
    Ensure all required columns exist.
    Fill any missing optional columns with sensible defaults.
    """
    for col in required_cols:
        if col not in df.columns:
            logger.warning(f"Column '{col}' missing — filling with default")
            if col in ("defense_triggered", "defense_active", "attack_success_binary"):
                df[col] = 0
            elif col in ("defense_confidence_score", "latency_ms"):
                df[col] = 0.0
            elif col in ("input_tokens", "output_tokens", "hop_index"):
                df[col] = 0
            else:
                df[col] = ""
    return df


def print_distribution(df: pd.DataFrame, title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(f"  Total rows: {len(df)}")
    for col in ["injection_type", "injection_outcome", "attack_success_binary", "defense_config"]:
        if col in df.columns:
            print(f"\n  {col}:")
            vc = df[col].fillna("").value_counts()
            for val, count in vc.items():
                pct = count / len(df) * 100
                print(f"    {str(val):<30} {count:>5}  ({pct:4.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge existing ReconMind dataset with AgentDojo-extracted data"
    )
    parser.add_argument(
        "--existing-runs",
        type=Path, default=Path("dataset/dataset_runs.csv"),
    )
    parser.add_argument(
        "--existing-events",
        type=Path, default=Path("dataset/dataset_events.csv"),
    )
    parser.add_argument(
        "--new-runs",
        type=Path, default=Path("dataset/agentdojo_runs.csv"),
    )
    parser.add_argument(
        "--new-events",
        type=Path, default=Path("dataset/agentdojo_events.csv"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path, default=Path("dataset/merged"),
        help="Output directory. Files will be named dataset_runs.csv and dataset_events.csv"
    )
    parser.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Skip run_id deduplication (not recommended)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force merge even if Track A and Track B eval reports do not exist yet"
    )
    args = parser.parse_args()
    
    # ── ROADMAP SAFETY GUARD ──────────────────────────────────────────
    if not args.force:
        track_a_results = Path("models/deep/results.json")
        track_b_results = Path("models/agentdojo/results.json")
        if not track_a_results.exists() or not track_b_results.exists():
            logger.error("❌ ROADMAP VIOLATION: You are attempting to merge datasets prematurely.")
            logger.error("To maintain strict experimental discipline, you must train and evaluate")
            logger.error("Track A (models/deep) and Track B (models/agentdojo) separately FIRST.")
            logger.error("Use --force if you absolutely know what you are doing.")
            sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # ── Load ──────────────────────────────────────────────────────────
    existing_runs   = _validate_csv(args.existing_runs,   REQUIRED_RUN_COLS,   "Existing runs")
    existing_events = _validate_csv(args.existing_events, REQUIRED_EVENT_COLS, "Existing events")

    if not args.new_runs.exists():
        logger.warning(
            f"AgentDojo runs not found at {args.new_runs} — "
            "run scripts/extract_agentdojo.py first. Saving existing data only."
        )
        merged_runs   = existing_runs
        merged_events = existing_events
    else:
        new_runs   = _validate_csv(args.new_runs,   REQUIRED_RUN_COLS,   "AgentDojo runs")
        new_events = _validate_csv(args.new_events, REQUIRED_EVENT_COLS, "AgentDojo events")

        # Align columns (fill any missing cols with defaults)
        existing_runs   = _align_columns(existing_runs,   REQUIRED_RUN_COLS)
        existing_events = _align_columns(existing_events, REQUIRED_EVENT_COLS)
        new_runs        = _align_columns(new_runs,        REQUIRED_RUN_COLS)
        new_events      = _align_columns(new_events,      REQUIRED_EVENT_COLS)

        # Tag source for traceability
        existing_runs["data_source"]   = "synthetic"
        existing_events["data_source"] = "synthetic"
        new_runs["data_source"]        = "agentdojo"
        new_events["data_source"]      = "agentdojo"

        # ── Merge ─────────────────────────────────────────────────────
        merged_runs   = pd.concat([existing_runs, new_runs],     ignore_index=True)
        merged_events = pd.concat([existing_events, new_events], ignore_index=True)

        # ── Deduplicate ───────────────────────────────────────────────
        if not args.no_dedupe:
            before = len(merged_runs)
            merged_runs   = merged_runs.drop_duplicates(subset=["run_id"])
            merged_events = merged_events[
                merged_events["run_id"].isin(merged_runs["run_id"])
            ]
            after = len(merged_runs)
            if before != after:
                logger.info(f"Deduplicated: removed {before - after} duplicate run_ids")

    # ── Validate that every event has a parent run ───────────────────
    orphan_count = len(
        merged_events[~merged_events["run_id"].isin(merged_runs["run_id"])]
    )
    if orphan_count:
        logger.warning(f"Found {orphan_count} orphan events (no matching run_id). Removing.")
        merged_events = merged_events[
            merged_events["run_id"].isin(merged_runs["run_id"])
        ]

    # ── Validate 3-hop constraint ─────────────────────────────────────
    hop_counts = merged_events.groupby("run_id").size()
    bad_runs = hop_counts[hop_counts != 3].index
    if len(bad_runs):
        logger.warning(
            f"{len(bad_runs)} runs have ≠ 3 events — removing them "
            f"(deep_model.py requires exactly 3 hops per run)"
        )
        merged_runs   = merged_runs[~merged_runs["run_id"].isin(bad_runs)]
        merged_events = merged_events[~merged_events["run_id"].isin(bad_runs)]

    # ── Save ──────────────────────────────────────────────────────────
    runs_out   = args.out_dir / "dataset_runs.csv"
    events_out = args.out_dir / "dataset_events.csv"

    merged_runs.to_csv(runs_out, index=False)
    merged_events.to_csv(events_out, index=False)

    # ── Report ────────────────────────────────────────────────────────
    print_distribution(merged_runs, "MERGED DATASET — Runs")

    print(f"\n{'='*60}")
    print("  OUTPUT FILES")
    print(f"{'='*60}")
    print(f"  Runs:   {runs_out}   ({len(merged_runs)} rows)")
    print(f"  Events: {events_out} ({len(merged_events)} rows)")

    print(f"\n  To retrain:")
    print(f"  .venv/bin/python analytics/train_model.py \\")
    print(f"    --dataset-dir {args.out_dir} \\")
    print(f"    --epochs 80 --no-cache")
    print()

    logger.info("Merge complete.")


if __name__ == "__main__":
    main()
