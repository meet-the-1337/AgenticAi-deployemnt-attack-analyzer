#!/usr/bin/env python3
"""
ReconMind — Standalone AgentDojo Training Script
=================================================
Trains the SAME BiLSTM architecture (from deep_model.py) but ONLY on
AgentDojo-generated data. No mixing with the original 533 synthetic runs.

Usage:
    .venv/bin/python analytics/train_agentdojo.py \
        --agentdojo-dir dataset \
        --prefix agentdojo_preview \
        --epochs 40 \
        --output-dir models/agentdojo

Reads:
    {agentdojo-dir}/{prefix}_runs.csv
    {agentdojo-dir}/{prefix}_events.csv

Outputs:
    {output-dir}/best_model.pt
    {output-dir}/results.json
    {output-dir}/text_embeddings.npy
"""

from __future__ import annotations
import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, WeightedRandomSampler
from torch.optim import AdamW
from torch.optim.lr_scheduler import OneCycleLR
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import f1_score, roc_auc_score, classification_report, confusion_matrix

# Add repo root to path so we can import deep_model components
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.deep_model import (
    TrainConfig,
    OUTCOME_LABELS, TYPE_LABELS, OUTCOME_MAP, TYPE_MAP,
    TABULAR_DIM, AGENT_ROLE_SIMPLE,
    build_tabular_vector, extract_text_pair,
    ReconMindSample, ReconMindDataset, ReconMindModel,
    MultiTaskLoss, compute_class_weights, evaluate, embed_texts,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# AGENTDOJO-SPECIFIC DATA LOADING
# ─────────────────────────────────────────────────────────────────

def load_agentdojo_samples(
    data_dir: Path,
    prefix: str,
) -> tuple[list[ReconMindSample], list[str]]:
    """
    Load AgentDojo-extracted CSVs and build ReconMindSamples.
    
    AgentDojo schema (runs):
        run_id, scenario_id, injection_type, injection_outcome,
        attack_success_binary, defense_config, attack_strength,
        attack_objective, source_framework, environment_domain,
        agent_config, duration_s, task_completed, metadata_json
        
    AgentDojo schema (events):
        run_id, hop_index, agent_role, agent_id, input_prompt_text,
        output_text, tool_called, input_tokens, output_tokens,
        latency_ms, defense_triggered, defense_active,
        defense_confidence_score
    """
    runs_path   = data_dir / f"{prefix}_runs.csv"
    events_path = data_dir / f"{prefix}_events.csv"
    
    if not runs_path.exists():
        raise FileNotFoundError(f"AgentDojo runs not found: {runs_path}")
    if not events_path.exists():
        raise FileNotFoundError(f"AgentDojo events not found: {events_path}")
    
    runs   = pd.read_csv(runs_path)
    events = pd.read_csv(events_path)
    
    logger.info(f"Loaded AgentDojo runs:   {len(runs)} rows from {runs_path}")
    logger.info(f"Loaded AgentDojo events: {len(events)} rows from {events_path}")
    
    # ── Clean NaN strings ──
    for col in ["tool_called", "agent_role", "input_prompt_text",
                "output_text", "injection_type", "injection_outcome",
                "defense_config", "attack_strength", "attack_objective"]:
        if col in runs.columns:
            runs[col] = runs[col].fillna("")
        if col in events.columns:
            events[col] = events[col].fillna("")
    
    # ── Drop runs with < 3 events (incomplete pipelines) ──
    event_counts = events.groupby("run_id").size()
    valid_runs = event_counts[event_counts == 3].index
    
    dropped_runs = len(runs) - len(valid_runs)
    if dropped_runs > 0:
        logger.warning(f"Dropped {dropped_runs} runs for not having exactly 3 hops (events).")
        
    runs   = runs[runs["run_id"].isin(valid_runs)].copy()
    events = events[events["run_id"].isin(valid_runs)].copy()
    
    logger.info(f"Valid runs (3 hops each): {len(runs)}")
    
    # Sort events by hop_index within each run
    events = events.sort_values(["run_id", "hop_index"])
    
    samples    = []
    text_pairs = []
    
    for _, run in runs.iterrows():
        rid = run["run_id"]
        hop_events = events[events["run_id"] == rid].reset_index(drop=True)
        
        if len(hop_events) != 3:
            continue
        
        # Build tabular matrix (3, 12)
        tab = np.stack([
            build_tabular_vector(hop_events.iloc[i])
            for i in range(3)
        ]).astype(np.float32)
        
        # Build text pairs for embedding
        pairs = [extract_text_pair(hop_events.iloc[i]) for i in range(3)]
        text_pairs.extend(pairs)
        
        # Labels
        outcome_str = str(run.get("injection_outcome", "clean") or "clean")
        type_str    = str(run.get("injection_type", "") or "")
        
        is_attack     = type_str != ""
        
        label_binary  = 1 if is_attack else 0
        label_outcome = OUTCOME_MAP.get(outcome_str, 0)
        label_type    = TYPE_MAP.get(type_str, -1)
        
        samples.append(ReconMindSample(
            run_id=rid,
            text_pairs=pairs,
            tabular=tab,
            label_binary=label_binary,
            label_outcome=label_outcome,
            label_type=label_type,   # -1 for clean runs, 0-3 for attacks
            is_attack=is_attack,
        ))
    
    # ── Print distribution summary ──
    n_attacks = sum(1 for s in samples if s.is_attack)
    n_clean   = len(samples) - n_attacks
    logger.info(f"\n{'='*60}")
    logger.info(f"  AGENTDOJO DATASET SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"  Total samples: {len(samples)}")
    logger.info(f"  Attacks:       {n_attacks}")
    logger.info(f"  Clean:         {n_clean}")
    logger.info(f"  Text pairs:    {len(text_pairs)}")
    
    # Attack type breakdown
    type_counts = {}
    for s in samples:
        if s.is_attack:
            for k, v in TYPE_MAP.items():
                if v == s.label_type and k:
                    type_counts[k] = type_counts.get(k, 0) + 1
    logger.info(f"\n  Attack type breakdown:")
    for t, c in sorted(type_counts.items()):
        logger.info(f"    {t:25s}: {c}")
    
    # Outcome breakdown
    outcome_counts = {}
    for s in samples:
        for k, v in OUTCOME_MAP.items():
            if v == s.label_outcome:
                outcome_counts[k] = outcome_counts.get(k, 0) + 1
    logger.info(f"\n  Outcome breakdown:")
    for o, c in sorted(outcome_counts.items()):
        logger.info(f"    {o:25s}: {c}")
    logger.info(f"{'='*60}\n")
    
    return samples, text_pairs


# ─────────────────────────────────────────────────────────────────
# TRAINING (same architecture, isolated data)
# ─────────────────────────────────────────────────────────────────

def train_agentdojo(
    data_dir: Path,
    prefix: str,
    output_dir: Path,
    epochs: int = 40,
    batch_size: int = 32,
    lr: float = 3e-4,
):
    """Train the BiLSTM exclusively on AgentDojo traces."""
    
    cfg = TrainConfig(
        dataset_dir=data_dir,
        output_dir=output_dir,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
    )
    
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    device = cfg.device if torch.cuda.is_available() else "cpu"
    logger.info(f"Training on: {device}")
    if device == "cuda":
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
    
    # ── Load ONLY AgentDojo data ──
    samples, text_pairs = load_agentdojo_samples(data_dir, prefix)
    
    if len(samples) < 10:
        logger.error(f"Only {len(samples)} samples found. Need at least 10 to train. "
                     "Generate more AgentDojo traces first.")
        return None, None
    
    # ── Embed texts ──
    embeddings = embed_texts(
        text_pairs,
        model_name=cfg.text_model,
        device=device,
        cache_path=output_dir / "text_embeddings.npy",
    )
    
    # ── Split (group by run_id — no data leakage) ──
    run_ids = np.array([s.run_id for s in samples])
    labels  = np.array([s.label_binary for s in samples])
    
    # Adjust test_size if dataset is small
    n = len(samples)
    test_frac = 0.2 if n >= 50 else 0.3
    val_frac  = 0.15 if n >= 50 else 0.2
    
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_frac, random_state=cfg.seed)
    train_idx, test_idx = next(splitter.split(samples, labels, groups=run_ids))
    
    # Further split train into train/val
    train_runs   = run_ids[train_idx]
    train_labels = labels[train_idx]
    val_split    = GroupShuffleSplit(n_splits=1, test_size=val_frac, random_state=cfg.seed)
    rel_tr, rel_val = next(val_split.split(
        train_idx, train_labels, groups=train_runs
    ))
    val_idx   = train_idx[rel_val]
    train_idx = train_idx[rel_tr]
    
    logger.info(f"Split: {len(train_idx)} train / {len(val_idx)} val / {len(test_idx)} test")
    
    def make_ds(idxs):
        return ReconMindDataset(
            [samples[i] for i in idxs],
            embeddings.reshape(len(samples), 3, cfg.text_dim)[idxs].reshape(-1, cfg.text_dim),
        )
    
    train_ds = make_ds(train_idx)
    val_ds   = make_ds(val_idx)
    test_ds  = make_ds(test_idx)
    
    # Weighted sampler for class imbalance
    sw = compute_class_weights([samples[i] for i in train_idx])
    sampler = WeightedRandomSampler(sw, num_samples=len(sw), replacement=True)
    
    train_loader = DataLoader(
        train_ds, batch_size=cfg.batch_size, sampler=sampler,
        num_workers=cfg.num_workers, pin_memory=cfg.pin_memory
    )
    val_loader  = DataLoader(val_ds,  batch_size=64, num_workers=cfg.num_workers)
    test_loader = DataLoader(test_ds, batch_size=64, num_workers=cfg.num_workers)
    
    # ── Model ──
    model    = ReconMindModel(cfg).to(device)
    mt_loss  = MultiTaskLoss(n_tasks=3).to(device)
    
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Model parameters: {n_params:,}")
    
    optimizer = AdamW(
        list(model.parameters()) + list(mt_loss.parameters()),
        lr=cfg.lr, weight_decay=cfg.weight_decay
    )
    scheduler = OneCycleLR(
        optimizer,
        max_lr=cfg.lr,
        steps_per_epoch=len(train_loader),
        epochs=cfg.epochs,
        pct_start=0.1,
    )
    
    # Class weights for losses (train-split only — no val/test leakage)
    train_samples = [samples[i] for i in train_idx]
    
    bin_counts   = np.bincount([s.label_binary for s in train_samples], minlength=2).astype(float)
    bin_cw       = torch.tensor(bin_counts.sum() / (2 * bin_counts + 1e-6), dtype=torch.float32).to(device)
    
    out_counts   = np.bincount([s.label_outcome for s in train_samples], minlength=4).astype(float)
    out_cw       = torch.tensor(out_counts.sum() / (4 * out_counts + 1e-6), dtype=torch.float32).to(device)
    
    type_counts  = np.bincount([s.label_type for s in train_samples if s.is_attack], minlength=len(TYPE_LABELS)).astype(float)
    type_cw      = torch.tensor(type_counts.sum() / (len(TYPE_LABELS) * type_counts + 1e-6), dtype=torch.float32).to(device)
    
    ce_binary  = nn.CrossEntropyLoss(weight=bin_cw)
    ce_outcome = nn.CrossEntropyLoss(weight=out_cw)
    ce_type    = nn.CrossEntropyLoss(weight=type_cw, ignore_index=-1)
    
    # ── Training loop ──
    best_val_f1 = 0.0
    history     = []
    
    for epoch in range(1, cfg.epochs + 1):
        model.train()
        epoch_loss = 0.0
        
        for batch in train_loader:
            te  = batch["text_emb"].to(device)
            tab = batch["tabular"].to(device)
            lb  = batch["label_binary"].to(device)
            lo  = batch["label_outcome"].to(device)
            lt  = batch["label_type"].to(device)
            ia  = batch["is_attack"].to(device)
            
            logit_b, logit_o, logit_t = model(te, tab)
            
            loss_b = ce_binary(logit_b, lb)
            loss_o = ce_outcome(logit_o, lo)
            
            # Type loss: ignore_index=-1 auto-excludes clean runs
            has_attacks = ia.any()
            if has_attacks:
                loss_t = ce_type(logit_t[ia], lt[ia])
            else:
                logger.info("  [DEBUG] Batch had 0 attacks. Masking Type loss.")
                loss_t = torch.tensor(0.0, device=device)
            
            # Use active_masks to prevent type log_var collapse on empty batches
            total = mt_loss(loss_b, loss_o, loss_t, active_masks=[True, True, has_attacks])
            
            optimizer.zero_grad()
            total.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            optimizer.step()
            scheduler.step()
            
            epoch_loss += total.item()
        
        avg_loss = epoch_loss / len(train_loader)
        
        # Validate every 5 epochs
        if epoch % 5 == 0 or epoch == cfg.epochs:
            val_metrics = evaluate(model, val_loader, device)
            composite_f1 = (
                val_metrics["binary_f1"] +
                val_metrics["outcome_macro_f1"] +
                val_metrics["type_macro_f1"]
            ) / 3.0
            
            # Extract current learned task weights (sigmas)
            with torch.no_grad():
                sigmas = torch.exp(0.5 * mt_loss.log_vars).cpu().tolist()
            
            logger.info(
                f"Epoch {epoch:03d} | loss={avg_loss:.4f} | "
                f"bin_f1={val_metrics['binary_f1']:.3f} | "
                f"out_f1={val_metrics['outcome_macro_f1']:.3f} | "
                f"type_f1={val_metrics['type_macro_f1']:.3f} | "
                f"composite={composite_f1:.3f}"
            )
            logger.info(
                f"          | sigmas: bin={sigmas[0]:.3f}, out={sigmas[1]:.3f}, type={sigmas[2]:.3f}"
            )
            
            history.append({
                "epoch": epoch,
                "loss": avg_loss,
                "sigma_binary": sigmas[0],
                "sigma_outcome": sigmas[1],
                "sigma_type": sigmas[2],
                **{k: v for k, v in val_metrics.items()
                   if isinstance(v, float)},
            })
            
            if composite_f1 > best_val_f1:
                best_val_f1 = composite_f1
                torch.save(
                    {
                        "model_state": model.state_dict(),
                        "mt_loss_state": mt_loss.state_dict(),
                        "cfg": cfg,
                        "outcome_labels": OUTCOME_LABELS,
                        "type_labels": TYPE_LABELS,
                        "epoch": epoch,
                        "val_composite_f1": composite_f1,
                        "data_source": "agentdojo_only",
                    },
                    output_dir / "best_model.pt"
                )
                logger.info(f"  ✅ New best model saved (composite F1={composite_f1:.3f})")
    
    # ── Final test evaluation ──
    logger.info("\n" + "="*50)
    logger.info("FINAL TEST EVALUATION (AgentDojo-Only Model)")
    logger.info("="*50)
    
    ckpt = torch.load(output_dir / "best_model.pt", map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state"])
    
    test_metrics = evaluate(model, test_loader, device)
    
    logger.info(f"Binary F1:       {test_metrics['binary_f1']:.4f}")
    logger.info(f"Binary ROC-AUC:  {test_metrics['binary_roc_auc']:.4f}")
    logger.info(f"Outcome Macro F1:{test_metrics['outcome_macro_f1']:.4f}")
    logger.info(f"Type Macro F1:   {test_metrics['type_macro_f1']:.4f}")
    logger.info("\nOutcome Report:\n" + test_metrics.get("outcome_report", ""))
    logger.info("\nType Report:\n" + test_metrics.get("type_report", ""))
    
    # Save results
    results = {
        "data_source": "agentdojo_only",
        "test_metrics": {k: v for k, v in test_metrics.items()
                         if isinstance(v, (float, int, list))},
        "training_history": history,
        "config": {k: str(v) for k, v in vars(cfg).items()},
        "dataset_info": {
            "total_samples": len(samples),
            "train": len(train_idx),
            "val": len(val_idx),
            "test": len(test_idx),
        }
    }
    with open(output_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\nResults saved to {output_dir}/results.json")
    
    print(f"\n{'='*50}")
    print(f"AGENTDOJO-ONLY TRAINING COMPLETE")
    print(f"{'='*50}")
    print(f"Binary Detection F1:    {test_metrics['binary_f1']:.4f}")
    print(f"Binary ROC-AUC:         {test_metrics['binary_roc_auc']:.4f}")
    print(f"Outcome Classification: {test_metrics['outcome_macro_f1']:.4f}")
    print(f"Type Classification:    {test_metrics['type_macro_f1']:.4f}")
    print(f"\nModel saved to: {output_dir}/best_model.pt")
    
    return model, test_metrics


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Train BiLSTM on AgentDojo data ONLY (no mixing)"
    )
    p.add_argument("--agentdojo-dir", type=str, default="dataset",
                   help="Directory containing the extracted AgentDojo CSVs")
    p.add_argument("--prefix", type=str, default="agentdojo_full",
                   help="Filename prefix (e.g. 'agentdojo_full' → agentdojo_full_runs.csv)")
    p.add_argument("--output-dir", type=str, default="models/agentdojo",
                   help="Where to save model & results (separate from models/deep)")
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=3e-4)
    return p.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("models/agentdojo/training.log", mode="w"),
        ]
    )
    
    args = parse_args()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    train_agentdojo(
        data_dir=Path(args.agentdojo_dir),
        prefix=args.prefix,
        output_dir=Path(args.output_dir),
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
    )
