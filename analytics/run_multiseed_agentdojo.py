#!/usr/bin/env python3
"""
ReconMind — Multi-Seed AgentDojo Training Script
=================================================
Evaluates the BiLSTM architecture using StratifiedGroupKFold
across multiple random seeds to ensure stability.
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
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.deep_model import (
    TrainConfig,
    OUTCOME_LABELS, TYPE_LABELS, OUTCOME_MAP, TYPE_MAP,
    TABULAR_DIM, AGENT_ROLE_SIMPLE,
    ReconMindSample, ReconMindDataset, ReconMindModel,
    MultiTaskLoss, compute_class_weights, evaluate, embed_texts,
)
from analytics.train_agentdojo import load_agentdojo_samples

logger = logging.getLogger(__name__)

def find_optimal_threshold(model, val_loader, device):
    """Evaluate on val_loader and find optimal binary threshold."""
    model.eval()
    all_probs = []
    all_labels = []
    with torch.no_grad():
        for batch in val_loader:
            te = batch["text_emb"].to(device)
            tab = batch["tabular"].to(device)
            lb = batch["label_binary"].numpy()
            
            logit_b, _, _ = model(te, tab)
            prob_b = F.softmax(logit_b, dim=-1)[:, 1].cpu().numpy()
            
            all_probs.extend(prob_b)
            all_labels.extend(lb)
            
    all_probs = np.array(all_probs)
    all_labels = np.array(all_labels)
    
    thresholds = np.arange(0.01, 1.0, 0.01)
    best_f1 = 0.0
    best_thresh = 0.5
    for t in thresholds:
        preds = (all_probs >= t).astype(int)
        f1 = f1_score(all_labels, preds, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = t
            
    return best_thresh, best_f1


def evaluate_with_threshold(model, loader, device, threshold):
    """Evaluate on a loader using a specific binary threshold."""
    model.eval()
    all_probs = []
    all_labels = []
    with torch.no_grad():
        for batch in loader:
            te = batch["text_emb"].to(device)
            tab = batch["tabular"].to(device)
            lb = batch["label_binary"].numpy()
            
            logit_b, _, _ = model(te, tab)
            prob_b = F.softmax(logit_b, dim=-1)[:, 1].cpu().numpy()
            
            all_probs.extend(prob_b)
            all_labels.extend(lb)
            
    all_probs = np.array(all_probs)
    all_labels = np.array(all_labels)
    
    preds = (all_probs >= threshold).astype(int)
    f1 = f1_score(all_labels, preds, zero_division=0)
    try:
        auc = roc_auc_score(all_labels, all_probs)
    except ValueError:
        auc = 0.0
    return f1, auc

def run_single_seed(seed, samples, embeddings, cfg):
    """Train and evaluate for a single seed."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    device = cfg.device if torch.cuda.is_available() else "cpu"
    
    run_ids = np.array([s.run_id for s in samples])
    type_labels = np.array([s.label_type for s in samples])
    
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    # Get 1 fold for test (20%)
    trainval_idx, test_idx = next(sgkf.split(samples, type_labels, groups=run_ids))
    
    trainval_runs = run_ids[trainval_idx]
    trainval_types = type_labels[trainval_idx]
    
    sgkf_val = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    # Get 1 fold from trainval for val (approx 16-20% of total)
    train_rel, val_rel = next(sgkf_val.split(trainval_idx, trainval_types, groups=trainval_runs))
    
    train_idx = trainval_idx[train_rel]
    val_idx = trainval_idx[val_rel]
    
    def make_ds(idxs):
        return ReconMindDataset(
            [samples[i] for i in idxs],
            embeddings.reshape(len(samples), 3, cfg.text_dim)[idxs].reshape(-1, cfg.text_dim),
        )
    
    train_ds = make_ds(train_idx)
    val_ds   = make_ds(val_idx)
    test_ds  = make_ds(test_idx)
    
    sw = compute_class_weights([samples[i] for i in train_idx])
    sampler = WeightedRandomSampler(sw, num_samples=len(sw), replacement=True)
    
    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, sampler=sampler, num_workers=0)
    val_loader  = DataLoader(val_ds,  batch_size=64, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=64, num_workers=0)
    
    model    = ReconMindModel(cfg).to(device)
    mt_loss  = MultiTaskLoss(n_tasks=3).to(device)
    
    optimizer = AdamW(list(model.parameters()) + list(mt_loss.parameters()), lr=cfg.lr, weight_decay=cfg.weight_decay)
    scheduler = OneCycleLR(optimizer, max_lr=cfg.lr, steps_per_epoch=len(train_loader), epochs=cfg.epochs, pct_start=0.1)
    
    train_samples = [samples[i] for i in train_idx]
    bin_counts = np.bincount([s.label_binary for s in train_samples], minlength=2).astype(float)
    bin_cw = torch.tensor(bin_counts.sum() / (2 * bin_counts + 1e-6), dtype=torch.float32).to(device)
    out_counts = np.bincount([s.label_outcome for s in train_samples], minlength=4).astype(float)
    out_cw = torch.tensor(out_counts.sum() / (4 * out_counts + 1e-6), dtype=torch.float32).to(device)
    type_counts = np.bincount([s.label_type for s in train_samples if s.is_attack and s.label_type >= 0], minlength=len(TYPE_LABELS)).astype(float)
    type_cw = torch.tensor(type_counts.sum() / (len(TYPE_LABELS) * type_counts + 1e-6), dtype=torch.float32).to(device)
    
    ce_binary = nn.CrossEntropyLoss(weight=bin_cw)
    ce_outcome = nn.CrossEntropyLoss(weight=out_cw)
    ce_type = nn.CrossEntropyLoss(weight=type_cw, ignore_index=-1)
    
    best_val_f1 = 0.0
    best_model_state = None
    
    for epoch in range(1, cfg.epochs + 1):
        model.train()
        for batch in train_loader:
            te = batch["text_emb"].to(device)
            tab = batch["tabular"].to(device)
            lb = batch["label_binary"].to(device)
            lo = batch["label_outcome"].to(device)
            lt = batch["label_type"].to(device)
            ia = batch["is_attack"].to(device)
            
            logit_b, logit_o, logit_t = model(te, tab)
            loss_b = ce_binary(logit_b, lb)
            loss_o = ce_outcome(logit_o, lo)
            
            has_attacks = ia.any()
            if has_attacks:
                loss_t = ce_type(logit_t[ia], lt[ia])
            else:
                loss_t = torch.tensor(0.0, device=device)
                
            total = mt_loss(loss_b, loss_o, loss_t, active_masks=[True, True, has_attacks])
            
            optimizer.zero_grad()
            total.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            optimizer.step()
            scheduler.step()
            
        if epoch % 5 == 0 or epoch == cfg.epochs:
            val_metrics = evaluate(model, val_loader, device)
            composite_f1 = (val_metrics["binary_f1"] + val_metrics["outcome_macro_f1"] + val_metrics["type_macro_f1"]) / 3.0
            if composite_f1 > best_val_f1:
                best_val_f1 = composite_f1
                best_model_state = model.state_dict()
                
    model.load_state_dict(best_model_state)
    
    # 1. Find optimal threshold on validation set
    opt_thresh, _ = find_optimal_threshold(model, val_loader, device)
    
    # 2. Apply on test set
    test_bin_f1_opt, test_bin_auc = evaluate_with_threshold(model, test_loader, device, opt_thresh)
    
    # 3. Evaluate multi-class metrics normally (they use argmax)
    test_metrics = evaluate(model, test_loader, device)
    
    return {
        "binary_f1": test_bin_f1_opt,
        "binary_auc": test_bin_auc,
        "type_macro_f1": test_metrics["type_macro_f1"],
        "outcome_macro_f1": test_metrics["outcome_macro_f1"],
        "optimal_threshold": opt_thresh,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agentdojo-dir", type=str, default="dataset")
    parser.add_argument("--prefix", type=str, default="agentdojo_banking_only")
    parser.add_argument("--epochs", type=int, default=40)
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    data_dir = Path(args.agentdojo_dir)
    samples, text_pairs = load_agentdojo_samples(data_dir, args.prefix)
    
    if len(samples) < 10:
        logger.error(f"Only {len(samples)} samples found.")
        return
        
    cfg = TrainConfig(epochs=args.epochs, num_workers=0)
    device = cfg.device if torch.cuda.is_available() else "cpu"
    
    logger.info("Embedding texts...")
    embeddings = embed_texts(text_pairs, model_name=cfg.text_model, device=device, cache_path=Path("models/agentdojo/text_embeddings.npy"))
    
    seeds = [42, 123, 7, 99, 2024]
    all_results = []
    
    logger.info("=" * 60)
    logger.info(f"STARTING MULTI-SEED EVALUATION (seeds: {seeds})")
    logger.info("=" * 60)
    
    for s in seeds:
        logger.info(f"Running seed {s}...")
        res = run_single_seed(s, samples, embeddings, cfg)
        logger.info(f"  Seed {s} -> Bin F1 (Opt Thresh): {res['binary_f1']:.4f} | Type Macro: {res['type_macro_f1']:.4f} (Thresh: {res['optimal_threshold']:.2f})")
        all_results.append(res)
        
    logger.info("=" * 60)
    logger.info("FINAL MULTI-SEED RESULTS")
    logger.info("=" * 60)
    
    bin_f1s = [r["binary_f1"] for r in all_results]
    bin_aucs = [r["binary_auc"] for r in all_results]
    type_f1s = [r["type_macro_f1"] for r in all_results]
    opt_threshs = [r["optimal_threshold"] for r in all_results]
    
    logger.info(f"Production Threshold (Mean Val Opt): {np.mean(opt_threshs):.2f} ± {np.std(opt_threshs):.2f}")
    logger.info(f"Binary F1:      {np.mean(bin_f1s):.4f} ± {np.std(bin_f1s):.4f}  (min={np.min(bin_f1s):.4f}, max={np.max(bin_f1s):.4f})")
    logger.info(f"Binary AUC:     {np.mean(bin_aucs):.4f} ± {np.std(bin_aucs):.4f}")
    logger.info(f"Type Macro F1:  {np.mean(type_f1s):.4f} ± {np.std(type_f1s):.4f}")

if __name__ == "__main__":
    main()
