#!/usr/bin/env python3
"""
ReconMind Ablation Pipeline — Rounds 1-4
=========================================
One script, one GPU session → 4 rounds of signal.
Each round changes exactly ONE thing. All share identical evaluation.

Usage (from repo root with .venv active):
    .venv/bin/python run_ablation.py \
        --prefix agentdojo_local \
        --epochs 40

Output:
    dataset/ablation_results.json   ← machine-readable log
    dataset/ablation_results.md     ← human-readable table
"""

from __future__ import annotations
import argparse, json, logging, sys, time
from copy import deepcopy
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, WeightedRandomSampler, Dataset
from torch.optim import AdamW
from torch.optim.lr_scheduler import OneCycleLR
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score, roc_auc_score, average_precision_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytics.deep_model import (
    TrainConfig, OUTCOME_LABELS, TYPE_LABELS, OUTCOME_MAP, TYPE_MAP,
    TABULAR_DIM, AGENT_ROLE_SIMPLE,
    build_tabular_vector, extract_text_pair,
    ReconMindSample, ReconMindModel, MultiTaskLoss, embed_texts,
)
from analytics.train_agentdojo import load_agentdojo_samples

logger = logging.getLogger(__name__)
SEEDS = [42, 123, 7, 99, 2024]


# ──────────────────────────────────────────────────────────────────────
# DATASET  (identical to existing, exposed here for clarity)
# ──────────────────────────────────────────────────────────────────────

class ReconMindDataset(Dataset):
    def __init__(self, samples: list[ReconMindSample], embeddings: np.ndarray, text_dim: int = 384):
        self.samples = samples
        self.embeddings = embeddings.reshape(len(samples), 3, text_dim).astype(np.float32)

    def __len__(self): return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        return {
            "text_emb":      torch.from_numpy(self.embeddings[idx]),
            "tabular":       torch.from_numpy(s.tabular),
            "label_binary":  torch.tensor(s.label_binary,  dtype=torch.long),
            "label_outcome": torch.tensor(s.label_outcome, dtype=torch.long),
            "label_type":    torch.tensor(s.label_type,    dtype=torch.long),
            "is_attack":     torch.tensor(s.is_attack,     dtype=torch.bool),
            "text_pairs":    s.text_pairs,
        }


def make_class_weights(samples: list[ReconMindSample], device: str):
    """Inverse-frequency weights for binary CrossEntropyLoss (train split only)."""
    labels = np.array([s.label_binary for s in samples])
    counts = np.bincount(labels, minlength=2).astype(float)
    cw = counts.sum() / (2.0 * counts + 1e-6)
    return torch.tensor(cw, dtype=torch.float32).to(device)


def make_sampler_weights(samples: list[ReconMindSample]) -> torch.Tensor:
    """WeightedRandomSampler weights — inverse frequency per class."""
    labels = np.array([s.label_binary for s in samples])
    counts = np.bincount(labels, minlength=2).astype(float)
    w = 1.0 / (counts + 1e-6)
    return torch.tensor([w[l] for l in labels], dtype=torch.float32)


# ──────────────────────────────────────────────────────────────────────
# HONEST EVALUATION
# ──────────────────────────────────────────────────────────────────────

def _collect_preds(model, loader, device, st_model=None):
    model.eval()
    if st_model is not None:
        st_model.eval()
    all_prob, all_bin, all_type_true, all_type_pred = [], [], [], []
    with torch.no_grad():
        for b in loader:
            if st_model is not None:
                te_list = []
                for hop in range(3):
                    texts = b["text_pairs"][hop]
                    features = st_model.tokenize(list(texts))
                    features = {k: v.to(device) for k, v in features.items() if isinstance(v, torch.Tensor)}
                    emb_hop = st_model(features)["sentence_embedding"]
                    te_list.append(emb_hop)
                te = torch.stack(te_list, dim=1)
            else:
                te  = b["text_emb"].to(device)
            tab = b["tabular"].to(device)
            lb  = b["label_binary"].numpy()
            ia  = b["is_attack"]
            logit_b, _, logit_t = model(te, tab)
            prob = F.softmax(logit_b, dim=1)[:, 1].cpu().numpy()
            all_prob.extend(prob); all_bin.extend(lb)
            if ia.any():
                all_type_pred.extend(logit_t[ia].argmax(1).cpu().tolist())
                all_type_true.extend(b["label_type"][ia].tolist())
    return (np.array(all_prob), np.array(all_bin),
            np.array(all_type_true), np.array(all_type_pred))


def evaluate_seed(model, val_loader, test_loader, device, st_model=None) -> dict:
    """Val-derived threshold, then apply to test. Returns full metrics dict."""
    val_prob, val_bin, _, _ = _collect_preds(model, val_loader, device, st_model)

    # Find optimal threshold on VAL
    best_t, best_f1 = 0.5, 0.0
    for t in np.arange(0.01, 0.99, 0.01):
        f = f1_score(val_bin, (val_prob >= t).astype(int), zero_division=0)
        if f > best_f1: best_f1, best_t = f, t

    test_prob, test_bin, type_true, type_pred = _collect_preds(model, test_loader, device, st_model)
    test_pred = (test_prob >= best_t).astype(int)

    try:   auc = roc_auc_score(test_bin, test_prob)
    except: auc = 0.0
    try:   pr_auc = average_precision_score(test_bin, test_prob)
    except: pr_auc = 0.0

    type_f1 = 0.0
    if len(type_true) > 0:
        type_f1 = f1_score(type_true, type_pred, average="macro", zero_division=0)

    return {
        "threshold": round(float(best_t), 3),
        "bin_f1":    round(float(f1_score(test_bin, test_pred, zero_division=0)), 4),
        "roc_auc":   round(float(auc), 4),
        "pr_auc":    round(float(pr_auc), 4),
        "type_f1":   round(float(type_f1), 4),
    }


# ──────────────────────────────────────────────────────────────────────
# TRAINING (shared across all rounds)
# ──────────────────────────────────────────────────────────────────────

def train_one_seed(
    seed: int,
    samples: list[ReconMindSample],
    embeddings: np.ndarray,
    cfg: TrainConfig,
    *,
    use_balanced_loss: bool = False,    # Round 2+
    logo_suite: Optional[str] = None,  # Round 3: held-out suite name
    unfreeze_encoder: bool = False,     # Round 4+
    st_model=None,                      # pass when unfreeze_encoder=True
) -> dict:
    device = cfg.device if torch.cuda.is_available() else "cpu"
    torch.manual_seed(seed); np.random.seed(seed)

    # ── Split: group on scenario_id (THE FIX) ──────────────────────
    # Round 3: LOGO — test = held-out suite, train+val = rest
    if logo_suite is not None:
        suites = np.array([s.run_id for s in samples])  # placeholder; real suite below
        # We need suite per sample — attach via run metadata
        suite_arr = np.array([getattr(s, "suite", "unknown") for s in samples])
        logo_mask = suite_arr == logo_suite
        if logo_mask.sum() == 0:
            raise ValueError(f"No samples for LOGO suite '{logo_suite}'")
        test_idx   = np.where(logo_mask)[0]
        trainval   = np.where(~logo_mask)[0]
        # Split trainval 85/15
        n_val = max(1, int(0.15 * len(trainval)))
        rng = np.random.RandomState(seed)
        perm = rng.permutation(trainval)
        val_idx   = perm[:n_val]
        train_idx = perm[n_val:]
    else:
        # scenario_id grouping (FIXED from run_id grouping)
        scenario_ids = np.array([getattr(s, "scenario_id", s.run_id) for s in samples])
        bin_labels   = np.array([s.label_binary for s in samples])
        sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        trainval_idx, test_idx = next(sgkf.split(samples, bin_labels, groups=scenario_ids))

        # Inner val split (also by scenario)
        inner_scenarios = scenario_ids[trainval_idx]
        inner_labels    = bin_labels[trainval_idx]
        sgkf_inner = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        rel_tr, rel_val = next(sgkf_inner.split(
            trainval_idx, inner_labels, groups=inner_scenarios
        ))
        train_idx = trainval_idx[rel_tr]
        val_idx   = trainval_idx[rel_val]

    def make_ds(idxs):
        return ReconMindDataset(
            [samples[i] for i in idxs],
            embeddings.reshape(len(samples), 3, cfg.text_dim)[idxs].reshape(-1, cfg.text_dim),
            text_dim=cfg.text_dim,
        )

    train_ds = make_ds(train_idx)
    val_ds   = make_ds(val_idx)
    test_ds  = make_ds(test_idx)

    sw = make_sampler_weights([samples[i] for i in train_idx])
    sampler = WeightedRandomSampler(sw, num_samples=len(sw), replacement=True)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, sampler=sampler, num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=64, num_workers=0)
    test_loader  = DataLoader(test_ds,  batch_size=64, num_workers=0)

    # ── Model & optimizer ──────────────────────────────────────────
    model   = ReconMindModel(cfg).to(device)
    mt_loss = MultiTaskLoss(n_tasks=3).to(device)

    train_samples = [samples[i] for i in train_idx]

    if use_balanced_loss:
        cw_bin = make_class_weights(train_samples, device)
    else:
        cw_bin = None

    ce_bin  = nn.CrossEntropyLoss(weight=cw_bin)
    ce_out  = nn.CrossEntropyLoss()
    ce_type = nn.CrossEntropyLoss(ignore_index=-1)

    if unfreeze_encoder and st_model is not None:
        # Unfreeze last 2 transformer layers of SentenceTransformer
        encoder = st_model[0].auto_model
        trainable_layers = list(encoder.encoder.layer[-2:])
        encoder_params = []
        for layer in trainable_layers:
            for p in layer.parameters():
                p.requires_grad = True
                encoder_params.append(p)
        logger.info(f"Seed {seed}: unfroze last 2 ST encoder layers")
        
        opt_params = [
            {"params": list(model.parameters()) + list(mt_loss.parameters()), "lr": cfg.lr},
            {"params": encoder_params, "lr": cfg.lr * 0.1}
        ]
        max_lrs = [cfg.lr, cfg.lr * 0.1]
    else:
        opt_params = list(model.parameters()) + list(mt_loss.parameters())
        max_lrs = cfg.lr

    optimizer = AdamW(opt_params, lr=cfg.lr, weight_decay=cfg.weight_decay)
    scheduler = OneCycleLR(
        optimizer, max_lr=max_lrs,
        steps_per_epoch=len(train_loader),
        epochs=cfg.epochs, pct_start=0.1,
    )

    best_val_f1 = 0.0
    best_state  = None

    for epoch in range(1, cfg.epochs + 1):
        model.train()
        if unfreeze_encoder and st_model is not None:
            st_model.train()
        for batch in train_loader:
            if unfreeze_encoder and st_model is not None:
                te_list = []
                for hop in range(3):
                    texts = batch["text_pairs"][hop]
                    features = st_model.tokenize(list(texts))
                    features = {k: v.to(device) for k, v in features.items() if isinstance(v, torch.Tensor)}
                    emb_hop = st_model(features)["sentence_embedding"]
                    te_list.append(emb_hop)
                te = torch.stack(te_list, dim=1)
            else:
                te  = batch["text_emb"].to(device)
            tab = batch["tabular"].to(device)
            lb  = batch["label_binary"].to(device)
            lo  = batch["label_outcome"].to(device)
            lt  = batch["label_type"].to(device)
            ia  = batch["is_attack"].to(device)

            logit_b, logit_o, logit_t = model(te, tab)
            loss_b = ce_bin(logit_b, lb)
            loss_o = ce_out(logit_o, lo)
            has_atk = ia.any()
            loss_t  = ce_type(logit_t[ia], lt[ia]) if has_atk else torch.tensor(0.0, device=device)

            total = mt_loss(loss_b, loss_o, loss_t, active_masks=[True, True, bool(has_atk)])
            optimizer.zero_grad(); total.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            if unfreeze_encoder and st_model is not None:
                nn.utils.clip_grad_norm_(st_model.parameters(), cfg.grad_clip)
            optimizer.step(); scheduler.step()

        if epoch % 5 == 0 or epoch == cfg.epochs:
            model.eval()
            vp, vb, _, _ = _collect_preds(model, val_loader, device, st_model if unfreeze_encoder else None)
            val_f1 = f1_score(vb, (vp >= 0.5).astype(int), zero_division=0)
            if val_f1 > best_val_f1:
                best_val_f1 = val_f1
                best_state  = deepcopy(model.state_dict())

    model.load_state_dict(best_state or model.state_dict())
    return evaluate_seed(model, val_loader, test_loader, device, st_model if unfreeze_encoder else None)


# ──────────────────────────────────────────────────────────────────────
# MULTI-SEED WRAPPER
# ──────────────────────────────────────────────────────────────────────

def run_round(
    round_id: int,
    label: str,
    change: str,
    samples: list[ReconMindSample],
    embeddings: np.ndarray,
    cfg: TrainConfig,
    **kwargs,
) -> dict:
    logger.info(f"\n{'='*60}")
    logger.info(f"ROUND {round_id}: {label}")
    logger.info(f"Change: {change}")
    logger.info(f"{'='*60}")

    seed_results = []
    for s in SEEDS:
        logger.info(f"  Seed {s}...")
        t0 = time.time()
        res = train_one_seed(s, samples, embeddings, cfg, **kwargs)
        res["seed"] = s
        res["elapsed_s"] = round(time.time() - t0, 1)
        seed_results.append(res)
        logger.info(f"    bin_f1={res['bin_f1']:.4f} roc_auc={res['roc_auc']:.4f} "
                    f"pr_auc={res['pr_auc']:.4f} type_f1={res['type_f1']:.4f} "
                    f"thresh={res['threshold']}")

    def mean(key): return round(float(np.mean([r[key] for r in seed_results])), 4)
    def std(key):  return round(float(np.std( [r[key] for r in seed_results])), 4)

    summary = {
        "round":       round_id,
        "label":       label,
        "change":      change,
        "n_seeds":     len(SEEDS),
        "bin_f1_mean": mean("bin_f1"), "bin_f1_std": std("bin_f1"),
        "roc_auc_mean":mean("roc_auc"),"roc_auc_std": std("roc_auc"),
        "pr_auc_mean": mean("pr_auc"), "pr_auc_std":  std("pr_auc"),
        "type_f1_mean":mean("type_f1"),"type_f1_std": std("type_f1"),
        "threshold_mean": mean("threshold"),
        "per_seed":    seed_results,
    }

    logger.info(f"\n  ── Round {round_id} Summary ──")
    logger.info(f"  Bin F1:   {summary['bin_f1_mean']:.4f} ± {summary['bin_f1_std']:.4f}")
    logger.info(f"  ROC-AUC:  {summary['roc_auc_mean']:.4f} ± {summary['roc_auc_std']:.4f}")
    logger.info(f"  PR-AUC:   {summary['pr_auc_mean']:.4f} ± {summary['pr_auc_std']:.4f}")
    logger.info(f"  Type F1:  {summary['type_f1_mean']:.4f} ± {summary['type_f1_std']:.4f}")
    logger.info(f"  Mean Threshold: {summary['threshold_mean']:.2f}  "
                f"(threshold=0.01 → model predicts everything as attack)")
    return summary


# ──────────────────────────────────────────────────────────────────────
# REPORT WRITER
# ──────────────────────────────────────────────────────────────────────

def write_markdown(results: list[dict], out_path: Path):
    lines = [
        "# ReconMind Ablation Results\n",
        "| Round | Label | Change | Bin F1 | ROC-AUC | PR-AUC | Type F1 | Threshold |",
        "|------:|-------|--------|-------:|--------:|-------:|--------:|----------:|",
    ]
    for r in results:
        lines.append(
            f"| {r['round']} | {r['label']} | {r['change']} "
            f"| {r['bin_f1_mean']:.4f}±{r['bin_f1_std']:.4f} "
            f"| {r['roc_auc_mean']:.4f}±{r['roc_auc_std']:.4f} "
            f"| {r['pr_auc_mean']:.4f}±{r['pr_auc_std']:.4f} "
            f"| {r['type_f1_mean']:.4f}±{r['type_f1_std']:.4f} "
            f"| {r['threshold_mean']:.2f} |"
        )
    lines += [
        "",
        "## Interpretation Guide",
        "- **Bin F1 threshold collapsed to ~0.01** → model predicts every trace as attack (imbalance artifact, not real detection)",
        "- **ROC-AUC < 0.65** → barely above random; model has not learned attack signal",
        "- **PR-AUC** is the honest metric when classes are severely imbalanced (use this over Bin F1)",
        "- **Type F1** tests whether attack *type* classification generalises (5 classes, macro-averaged)",
    ]
    out_path.write_text("\n".join(lines))
    logger.info(f"Markdown report saved to {out_path}")


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix",   default="agentdojo_local")
    parser.add_argument("--data-dir", default="dataset")
    parser.add_argument("--epochs",   type=int, default=40)
    parser.add_argument("--rounds",   default="1,2,3,4",
                        help="Comma-separated round numbers to run, e.g. '1,2'")
    parser.add_argument("--logo-suite", default="banking",
                        help="Suite name to hold out in Round 3 LOGO eval")
    args = parser.parse_args()

    rounds_to_run = [int(x) for x in args.rounds.split(",")]

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("dataset/ablation.log", mode="w"),
        ],
    )

    data_dir   = Path(args.data_dir)
    out_json   = data_dir / "ablation_results.json"
    out_md     = data_dir / "ablation_results.md"

    # ── Load samples ONCE (shared across all rounds) ──────────────
    logger.info("Loading AgentDojo samples...")
    samples, text_pairs = load_agentdojo_samples(data_dir, args.prefix)

    # Attach scenario_id to each sample (needed for correct grouping)
    runs_df = pd.read_csv(data_dir / f"{args.prefix}_runs.csv")
    sid_map = dict(zip(runs_df["run_id"], runs_df["scenario_id"]))
    suite_map = dict(zip(runs_df["run_id"], runs_df["environment_domain"]))
    for s in samples:
        s.scenario_id = sid_map.get(s.run_id, s.run_id)
        s.suite = suite_map.get(s.run_id, "unknown")

    cfg = TrainConfig(epochs=args.epochs, num_workers=0)
    device = cfg.device if torch.cuda.is_available() else "cpu"

    logger.info("Embedding texts (cached after first run)...")
    embeddings = embed_texts(
        text_pairs, model_name=cfg.text_model, device=device,
        cache_path=Path("models/agentdojo/text_embeddings.npy"),
    )

    # ── Dataset snapshot ──────────────────────────────────────────
    logger.info(f"\n{'='*60}")
    logger.info(f"DATASET SNAPSHOT")
    logger.info(f"{'='*60}")
    logger.info(f"  Total samples:      {len(samples)}")
    logger.info(f"  Unique run_ids:     {len(set(s.run_id for s in samples))}")
    logger.info(f"  Unique scenario_ids:{len(set(s.scenario_id for s in samples))}")
    n_atk = sum(1 for s in samples if s.is_attack)
    n_cln = len(samples) - n_atk
    logger.info(f"  Attacks:            {n_atk} ({100*n_atk/len(samples):.1f}%)")
    logger.info(f"  Clean:              {n_cln} ({100*n_cln/len(samples):.1f}%)")
    logger.info(f"  Suites:             {dict(pd.Series([s.suite for s in samples]).value_counts())}")
    logger.info(f"{'='*60}\n")

    # ── Run rounds ────────────────────────────────────────────────
    all_results = []

    if 1 in rounds_to_run:
        r = run_round(
            1, "True Baseline",
            "scenario_id grouping (fixed). No other changes.",
            samples, embeddings, cfg,
            use_balanced_loss=False,
        )
        all_results.append(r)

    if 2 in rounds_to_run:
        r = run_round(
            2, "Balanced Loss",
            "Round 1 + inverse-freq CrossEntropyLoss weight on binary head.",
            samples, embeddings, cfg,
            use_balanced_loss=True,
        )
        all_results.append(r)

    if 3 in rounds_to_run:
        r = run_round(
            3, f"LOGO ({args.logo_suite})",
            f"Round 2 model. Train on all suites except '{args.logo_suite}', test on '{args.logo_suite}' only.",
            samples, embeddings, cfg,
            use_balanced_loss=True,
            logo_suite=args.logo_suite,
        )
        all_results.append(r)

    if 4 in rounds_to_run:
        from sentence_transformers import SentenceTransformer
        st_model = SentenceTransformer(cfg.text_model, device=device)
        r = run_round(
            4, "Unfreeze Encoder (last 2 layers)",
            "Round 2 settings + fine-tune last 2 SentenceTransformer layers.",
            samples, embeddings, cfg,
            use_balanced_loss=True,
            unfreeze_encoder=True,
            st_model=st_model,
        )
        all_results.append(r)

    # ── Save results ──────────────────────────────────────────────
    # Strip non-serializable from per_seed if any
    clean_results = json.loads(json.dumps(all_results, default=str))
    out_json.write_text(json.dumps(clean_results, indent=2))
    logger.info(f"\nResults saved to {out_json}")

    write_markdown(all_results, out_md)

    # ── Terminal summary ──────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"{'Round':<8} {'Label':<30} {'Bin F1':>10} {'ROC-AUC':>10} {'PR-AUC':>10} {'Thresh':>8}")
    print(f"{'='*70}")
    for r in all_results:
        flag = " ← THRESHOLD COLLAPSE" if r["threshold_mean"] <= 0.05 else ""
        print(f"{r['round']:<8} {r['label']:<30} "
              f"{r['bin_f1_mean']:>7.4f}±{r['bin_f1_std']:.3f} "
              f"{r['roc_auc_mean']:>10.4f} "
              f"{r['pr_auc_mean']:>10.4f} "
              f"{r['threshold_mean']:>8.2f}{flag}")
    print(f"{'='*70}")
    print(f"\nFull results: {out_json}")
    print(f"Report:       {out_md}")


if __name__ == "__main__":
    main()
