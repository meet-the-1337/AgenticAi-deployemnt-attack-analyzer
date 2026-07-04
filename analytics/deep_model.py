# reconmind/analytics/deep_model.py
"""
ReconMind Deep Learning Pipeline
Multi-task sequence model over 3-hop agent traces.
Architecture:
  Text → SentenceTransformer embeddings (frozen)
  Tabular features → MLP encoder
  Concatenated per hop → BiLSTM over 3 hops
  3 task heads:
    1. Binary: attack_success_binary
    2. Multiclass (4): injection_outcome (clean/ignored/partial/full_success)
    3. Multiclass (4): injection_type (direct/indirect/memory/tool_misuse)
"""

from __future__ import annotations
import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torch.optim import AdamW
from torch.optim.lr_scheduler import OneCycleLR
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    f1_score, roc_auc_score, classification_report,
    confusion_matrix
)
from sentence_transformers import SentenceTransformer
import joblib

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

@dataclass
class TrainConfig:
    # Paths
    dataset_dir: Path = Path("dataset")
    output_dir: Path = Path("models/deep")
    
    # Model
    text_model: str = "all-MiniLM-L6-v2"   # 384-dim, fast, good quality
    text_dim: int = 384
    tabular_hidden: int = 128
    lstm_hidden: int = 256
    lstm_layers: int = 2
    dropout: float = 0.3
    
    # Training
    batch_size: int = 32
    epochs: int = 60
    lr: float = 3e-4
    weight_decay: float = 1e-4
    grad_clip: float = 1.0
    
    # Multi-task loss weights
    # Tune if one task dominates — start equal
    loss_weight_binary: float = 1.0
    loss_weight_outcome: float = 1.0
    loss_weight_type: float = 0.8     # slightly lower, harder task
    
    # Hardware
    device: str = "cuda"
    num_workers: int = 4
    pin_memory: bool = True
    
    # Reproducibility
    seed: int = 42


CFG = TrainConfig()

# ─────────────────────────────────────────────
# LABEL MAPS  (fixed — don't infer from data)
# ─────────────────────────────────────────────

OUTCOME_LABELS  = ["clean", "ignored", "partial", "full_success"]
TYPE_LABELS     = ["direct_injection", "indirect_injection",
                   "memory_poisoning", "tool_misuse"]
DEFENSE_LABELS  = ["none", "heuristic", "judge"]
STRENGTH_LABELS = ["subtle", "moderate", "blatant"]
OBJECTIVE_LABELS= ["unauthorized_action", "data_exfiltration",
                   "denial_of_service"]
AGENT_LABELS    = ["intake", "retrieval", "action",
                   "intake_agent", "retrieval_agent", "action_agent"]

def make_label_encoder(labels: list[str]) -> dict[str, int]:
    return {v: i for i, v in enumerate(labels)}

OUTCOME_MAP  = make_label_encoder(OUTCOME_LABELS)
TYPE_MAP     = make_label_encoder(TYPE_LABELS)
DEFENSE_MAP  = make_label_encoder(DEFENSE_LABELS)
STRENGTH_MAP = make_label_encoder(STRENGTH_LABELS)
OBJ_MAP      = make_label_encoder(OBJECTIVE_LABELS)


# ─────────────────────────────────────────────
# FEATURE EXTRACTION
# ─────────────────────────────────────────────

TABULAR_FEATURES_PER_HOP = [
    # numeric — already in events table
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "defense_triggered",
    "defense_active",
    "defense_confidence_score",
    # derived
    "token_ratio",          # output_tokens / (input_tokens + 1)
    "is_tool_call",         # 1 if tool_called is not null
    "is_escalate",          # 1 if tool_called == escalate_to_admin
    "is_send_email",        # 1 if tool_called == send_email
    "agent_role_encoded",   # intake=0 retrieval=1 action=2
    "hop_index",
]
TABULAR_DIM = len(TABULAR_FEATURES_PER_HOP)   # 12

AGENT_ROLE_SIMPLE = {
    "intake": 0, "intake_agent": 0,
    "retrieval": 1, "retrieval_agent": 1,
    "action": 2, "action_agent": 2,
}


def build_tabular_vector(event: pd.Series) -> np.ndarray:
    tool = str(event.get("tool_called", "") or "")
    agent = str(event.get("agent_role", "") or "")
    inp   = float(event.get("input_tokens",  0) or 0)
    out   = float(event.get("output_tokens", 0) or 0)
    
    vec = np.array([
        float(event.get("latency_ms",             0) or 0) / 1000.0,
        inp / 500.0,
        out / 500.0,
        float(event.get("defense_triggered",       0) or 0),
        float(event.get("defense_active",          0) or 0),
        float(event.get("defense_confidence_score",0) or 0),
        out / (inp + 1.0),
        1.0 if tool else 0.0,
        1.0 if tool == "escalate_to_admin" else 0.0,
        1.0 if tool == "send_email" else 0.0,
        float(AGENT_ROLE_SIMPLE.get(agent, 0)),
        float(event.get("hop_index", 0) or 0) / 2.0,
    ], dtype=np.float32)
    return vec


def extract_text_pair(event: pd.Series) -> str:
    """
    Concatenate input + output for embedding.
    SentenceTransformer handles truncation automatically.
    Format: [INPUT] {text} [OUTPUT] {text}
    Helps the model distinguish input vs output semantics.
    """
    inp = str(event.get("input_prompt_text", "") or "")[:512]
    out = str(event.get("output_text",       "") or "")[:512]
    return f"[INPUT] {inp} [OUTPUT] {out}"


# ─────────────────────────────────────────────
# DATASET
# ─────────────────────────────────────────────

@dataclass
class ReconMindSample:
    run_id:        str
    text_pairs:    list[str]          # 3 strings, one per hop
    tabular:       np.ndarray         # (3, TABULAR_DIM)
    label_binary:  int                # 0/1
    label_outcome: int                # 0-3
    label_type:    int                # 0-3 or -1 for clean runs
    is_attack:     bool               # False for clean runs


class ReconMindDataset(Dataset):
    def __init__(
        self,
        samples: list[ReconMindSample],
        text_embeddings: np.ndarray,  # precomputed (N*3, 384)
    ):
        self.samples = samples
        # reshape to (N, 3, 384)
        self.embeddings = text_embeddings.reshape(
            len(samples), 3, CFG.text_dim
        ).astype(np.float32)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        return {
            "text_emb":      torch.from_numpy(self.embeddings[idx]),   # (3, 384)
            "tabular":       torch.from_numpy(s.tabular),              # (3, 12)
            "label_binary":  torch.tensor(s.label_binary,  dtype=torch.long),
            "label_outcome": torch.tensor(s.label_outcome, dtype=torch.long),
            "label_type":    torch.tensor(s.label_type,    dtype=torch.long),
            "is_attack":     torch.tensor(s.is_attack,     dtype=torch.bool),
        }


# ─────────────────────────────────────────────
# MODEL
# ─────────────────────────────────────────────

class TabularEncoder(nn.Module):
    """MLP that projects tabular features per hop to a fixed dim."""
    def __init__(self, in_dim: int, out_dim: int, dropout: float):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, 64),
            nn.LayerNorm(64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, out_dim),
            nn.GELU(),
        )
    def forward(self, x):     # x: (B, 3, in_dim)
        return self.net(x)    # (B, 3, out_dim)


class ReconMindModel(nn.Module):
    def __init__(self, cfg: TrainConfig):
        super().__init__()
        self.cfg = cfg
        
        tab_proj_dim = 64
        seq_input_dim = cfg.text_dim + tab_proj_dim  # 384 + 64 = 448
        
        # Per-hop encoders
        self.tab_encoder = TabularEncoder(
            TABULAR_DIM, tab_proj_dim, cfg.dropout
        )
        
        # Sequence encoder — BiLSTM over 3 hops
        self.lstm = nn.LSTM(
            input_size=seq_input_dim,
            hidden_size=cfg.lstm_hidden,
            num_layers=cfg.lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=cfg.dropout if cfg.lstm_layers > 1 else 0.0,
        )
        # BiLSTM output dim = 2 * lstm_hidden
        lstm_out_dim = cfg.lstm_hidden * 2
        
        # Attention pooling over sequence
        self.attn = nn.Linear(lstm_out_dim, 1)
        
        self.dropout = nn.Dropout(cfg.dropout)
        
        # Task heads
        head_in = lstm_out_dim
        
        self.head_binary = nn.Sequential(
            nn.Linear(head_in, 128),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(128, 2),          # 0=clean, 1=attack
        )
        self.head_outcome = nn.Sequential(
            nn.Linear(head_in, 128),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(128, 4),          # clean/ignored/partial/full_success
        )
        self.head_type = nn.Sequential(
            nn.Linear(head_in, 128),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(128, 4),          # 4 attack types
        )
    
    def forward(self, text_emb, tabular):
        # text_emb: (B, 3, 384)
        # tabular:  (B, 3, 12)
        
        tab_enc = self.tab_encoder(tabular)         # (B, 3, 64)
        seq = torch.cat([text_emb, tab_enc], dim=-1) # (B, 3, 448)
        
        lstm_out, _ = self.lstm(seq)                # (B, 3, 512)
        
        # Attention pooling
        attn_w = self.attn(lstm_out).squeeze(-1)    # (B, 3)
        attn_w = F.softmax(attn_w, dim=-1)
        pooled = (lstm_out * attn_w.unsqueeze(-1)).sum(dim=1)  # (B, 512)
        pooled = self.dropout(pooled)
        
        return (
            self.head_binary(pooled),   # (B, 2)
            self.head_outcome(pooled),  # (B, 4)
            self.head_type(pooled),     # (B, 4)
        )


# ─────────────────────────────────────────────
# LOSS
# ─────────────────────────────────────────────

class MultiTaskLoss(nn.Module):
    """
    Learnable task weighting via log-variance (Kendall et al. 2018).
    Starts at equal weights but adapts during training.
    Overrides CFG loss weights with learned values.
    """
    def __init__(self, n_tasks: int = 3):
        super().__init__()
        # log(sigma^2) per task, init = 0 → sigma = 1
        self.log_vars = nn.Parameter(torch.zeros(n_tasks))
    
    def forward(
        self,
        loss_binary: torch.Tensor,
        loss_outcome: torch.Tensor,
        loss_type: torch.Tensor,
    ) -> torch.Tensor:
        losses = torch.stack([loss_binary, loss_outcome, loss_type])
        # L_i / (2 * sigma_i^2) + log(sigma_i)
        precision = torch.exp(-self.log_vars)
        total = (precision * losses + self.log_vars).sum()
        return total


# ─────────────────────────────────────────────
# DATA LOADING + EMBEDDING
# ─────────────────────────────────────────────

def load_samples(
    dataset_dir: Path,
) -> tuple[list[ReconMindSample], list[str]]:
    """
    Load CSVs, align events to runs, build sample list.
    Returns samples + flat list of text pairs for bulk embedding.
    """
    runs   = pd.read_csv(dataset_dir / "dataset_runs.csv")
    events = pd.read_csv(dataset_dir / "dataset_events.csv")
    
    # Clean NaN strings
    for col in ["tool_called", "memory_ops_summary", "agent_role",
                "input_prompt_text", "output_text", "injection_type",
                "injection_outcome", "defense_config", "attack_strength",
                "attack_objective"]:
        if col in runs.columns:
            runs[col] = runs[col].fillna("")
        if col in events.columns:
            events[col] = events[col].fillna("")
    
    # Drop runs with < 3 events (incomplete pipelines)
    event_counts = events.groupby("run_id").size()
    valid_runs = event_counts[event_counts == 3].index
    runs = runs[runs["run_id"].isin(valid_runs)].copy()
    events = events[events["run_id"].isin(valid_runs)].copy()
    
    # Sort events by hop_index within each run
    events = events.sort_values(["run_id", "hop_index"])
    
    samples   = []
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
        
        label_binary  = int(run.get("attack_success_binary", 0) or 0)
        label_outcome = OUTCOME_MAP.get(outcome_str, 0)
        label_type    = TYPE_MAP.get(type_str, -1)   # -1 for clean
        is_attack     = type_str != ""
        
        samples.append(ReconMindSample(
            run_id=rid,
            text_pairs=pairs,
            tabular=tab,
            label_binary=label_binary,
            label_outcome=label_outcome,
            label_type=label_type if label_type >= 0 else 0,
            is_attack=is_attack,
        ))
    
    logger.info(f"Loaded {len(samples)} samples, {len(text_pairs)} text pairs")
    return samples, text_pairs


def embed_texts(
    text_pairs: list[str],
    model_name: str,
    device: str,
    cache_path: Optional[Path] = None,
) -> np.ndarray:
    """
    Bulk embed all text pairs. Caches to disk so re-runs are instant.
    """
    if cache_path and cache_path.exists():
        logger.info(f"Loading cached embeddings from {cache_path}")
        return np.load(cache_path)
    
    logger.info(f"Embedding {len(text_pairs)} texts with {model_name}...")
    embedder = SentenceTransformer(model_name, device=device)
    
    embeddings = embedder.encode(
        text_pairs,
        batch_size=256,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,    # cosine similarity ready
    )
    
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache_path, embeddings)
        logger.info(f"Cached embeddings to {cache_path}")
    
    return embeddings  # (N*3, 384)


# ─────────────────────────────────────────────
# TRAIN / EVAL LOOPS
# ─────────────────────────────────────────────

def compute_class_weights(
    samples: list[ReconMindSample],
) -> torch.Tensor:
    """Inverse frequency weights for binary sampler."""
    labels = [s.label_binary for s in samples]
    counts = np.bincount(labels, minlength=2).astype(float)
    weights = 1.0 / (counts + 1e-6)
    sample_weights = torch.tensor(
        [weights[l] for l in labels], dtype=torch.float32
    )
    return sample_weights


def evaluate(
    model: nn.Module,
    loader: DataLoader,
    device: str,
) -> dict:
    model.eval()
    all_bin_pred, all_bin_true   = [], []
    all_out_pred, all_out_true   = [], []
    all_type_pred, all_type_true = [], []
    all_bin_prob = []
    
    with torch.no_grad():
        for batch in loader:
            te  = batch["text_emb"].to(device)
            tab = batch["tabular"].to(device)
            
            logit_b, logit_o, logit_t = model(te, tab)
            
            all_bin_pred.extend(logit_b.argmax(1).cpu().tolist())
            all_bin_true.extend(batch["label_binary"].tolist())
            all_bin_prob.extend(
                F.softmax(logit_b, dim=1)[:, 1].cpu().tolist()
            )
            all_out_pred.extend(logit_o.argmax(1).cpu().tolist())
            all_out_true.extend(batch["label_outcome"].tolist())
            
            # Type: only evaluate on attack runs
            is_atk = batch["is_attack"]
            if is_atk.any():
                all_type_pred.extend(
                    logit_t[is_atk].argmax(1).cpu().tolist()
                )
                all_type_true.extend(
                    batch["label_type"][is_atk].tolist()
                )
    
    metrics = {}
    
    # Task 1: binary
    metrics["binary_f1"]      = f1_score(all_bin_true, all_bin_pred, average="binary", zero_division=0)
    metrics["binary_roc_auc"] = roc_auc_score(all_bin_true, all_bin_prob) if len(set(all_bin_true)) > 1 else 0.0
    
    # Task 2: outcome
    metrics["outcome_macro_f1"] = f1_score(all_out_true, all_out_pred, average="macro", zero_division=0)
    metrics["outcome_report"]   = classification_report(
        all_out_true, all_out_pred,
        labels=list(range(len(OUTCOME_LABELS))),
        target_names=OUTCOME_LABELS, zero_division=0
    )
    
    # Task 3: attack type
    if all_type_true:
        metrics["type_macro_f1"] = f1_score(all_type_true, all_type_pred, average="macro", zero_division=0)
        metrics["type_report"]   = classification_report(
            all_type_true, all_type_pred,
            labels=list(range(len(TYPE_LABELS))),
            target_names=TYPE_LABELS, zero_division=0
        )
        metrics["type_confusion"] = confusion_matrix(
            all_type_true, all_type_pred
        ).tolist()
    else:
        metrics["type_macro_f1"] = 0.0
    
    return metrics


def train(cfg: TrainConfig = CFG):
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    device = cfg.device if torch.cuda.is_available() else "cpu"
    logger.info(f"Training on: {device}")
    if device == "cuda":
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
    
    # ── Load data ──────────────────────────────
    samples, text_pairs = load_samples(cfg.dataset_dir)
    
    embeddings = embed_texts(
        text_pairs,
        model_name=cfg.text_model,
        device=device,
        cache_path=cfg.output_dir / "text_embeddings.npy",
    )
    
    # ── Split (group by run_id — no leakage) ──
    run_ids = np.array([s.run_id for s in samples])
    labels  = np.array([s.label_binary for s in samples])
    
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=cfg.seed)
    train_idx, test_idx = next(splitter.split(samples, labels, groups=run_ids))
    
    # Further split train into train/val 85/15
    train_runs   = run_ids[train_idx]
    train_labels = labels[train_idx]
    val_split    = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=cfg.seed)
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
    
    # ── Model ──────────────────────────────────
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
    
    # Class weights for losses
    # Binary: upweight attack class
    bin_counts   = np.bincount([s.label_binary for s in samples], minlength=2).astype(float)
    bin_cw       = torch.tensor(bin_counts.sum() / (2 * bin_counts + 1e-6), dtype=torch.float32).to(device)
    
    out_counts   = np.bincount([s.label_outcome for s in samples], minlength=4).astype(float)
    out_cw       = torch.tensor(out_counts.sum() / (4 * out_counts + 1e-6), dtype=torch.float32).to(device)
    
    type_counts  = np.bincount([s.label_type for s in samples if s.is_attack], minlength=4).astype(float)
    type_cw      = torch.tensor(type_counts.sum() / (4 * type_counts + 1e-6), dtype=torch.float32).to(device)
    
    ce_binary  = nn.CrossEntropyLoss(weight=bin_cw)
    ce_outcome = nn.CrossEntropyLoss(weight=out_cw)
    ce_type    = nn.CrossEntropyLoss(weight=type_cw)
    
    # ── Training loop ──────────────────────────
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
            
            # Type loss only on attack runs (clean has no type)
            if ia.any():
                loss_t = ce_type(logit_t[ia], lt[ia])
            else:
                # Keep computation graph connected by computing dummy loss with 0 weight
                loss_t = ce_type(logit_t, torch.zeros(logit_t.size(0), dtype=torch.long, device=device)) * 0.0
            
            total = mt_loss(loss_b, loss_o, loss_t)
            
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
            
            logger.info(
                f"Epoch {epoch:03d} | loss={avg_loss:.4f} | "
                f"bin_f1={val_metrics['binary_f1']:.3f} | "
                f"out_f1={val_metrics['outcome_macro_f1']:.3f} | "
                f"type_f1={val_metrics['type_macro_f1']:.3f} | "
                f"composite={composite_f1:.3f}"
            )
            
            history.append({
                "epoch": epoch,
                "loss": avg_loss,
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
                    },
                    cfg.output_dir / "best_model.pt"
                )
                logger.info(f"  ✅ New best model saved (composite F1={composite_f1:.3f})")
    
    # ── Final test evaluation ───────────────────
    logger.info("\n" + "="*50)
    logger.info("FINAL TEST EVALUATION")
    logger.info("="*50)
    
    ckpt = torch.load(cfg.output_dir / "best_model.pt", map_location=device, weights_only=False)
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
        "test_metrics": {k: v for k, v in test_metrics.items() 
                         if isinstance(v, (float, int, list))},
        "training_history": history,
        "config": {
            k: str(v) for k, v in vars(cfg).items()
        },
        "dataset_info": {
            "total_samples": len(samples),
            "train": len(train_idx),
            "val": len(val_idx),
            "test": len(test_idx),
        }
    }
    with open(cfg.output_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\nResults saved to {cfg.output_dir}/results.json")
    return model, test_metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train()
