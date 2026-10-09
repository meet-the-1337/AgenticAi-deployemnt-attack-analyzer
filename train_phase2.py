"""
Phase 2 training script.
Run on college GPU. Trains + evaluates across 5 seeds on the EXPANDED
AgentDojo dataset (same architecture, more data — isolates data-volume effect).

BEFORE RUNNING: update CSV_PATH and confirm column names match your extractor output.
"""

import torch, torch.nn as nn, numpy as np, pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
from sentence_transformers import SentenceTransformer
from sklearn.metrics import f1_score, roc_auc_score
import json

# ---------- CONFIG ----------
CSV_PATH = "dataset/agentdojo_local_runs.csv"   
EVENTS_PATH = "dataset/agentdojo_local_events.csv"
SEEDS = [42, 123, 7, 99, 2024]
TABULAR_DIM = 10   # Reduced from 12 (dropped dead features: tool_error, tool_resp_length)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ---------- MODEL (unchanged architecture) ----------
class ReconMindModel(nn.Module):
    def __init__(self, tab_dim=TABULAR_DIM, n_type=5):
        super().__init__()
        self.tab_encoder = nn.Sequential(nn.Linear(tab_dim, 64), nn.ReLU(), nn.Dropout(0.3))
        self.lstm = nn.LSTM(384 + 64, 256, num_layers=2, batch_first=True,
                             bidirectional=True, dropout=0.3)
        self.attn = nn.Linear(512, 1)
        self.pre_head_dropout = nn.Dropout(0.2)
        self.head_binary = nn.Sequential(nn.Linear(512, 128), nn.GELU(), nn.Linear(128, 2))
        self.head_outcome = nn.Sequential(nn.Linear(512, 128), nn.GELU(), nn.Linear(128, 4))
        self.head_type = nn.Sequential(nn.Linear(512, 128), nn.GELU(), nn.Linear(128, n_type))

    def forward(self, text_emb, tab_feat):  # [B,3,384], [B,3,tab_dim]
        tab_out = self.tab_encoder(tab_feat)
        seq = torch.cat([text_emb, tab_out], dim=-1)
        lstm_out, _ = self.lstm(seq)                       # [B,3,512]
        attn_w = torch.softmax(self.attn(lstm_out), dim=1)  # [B,3,1]
        pooled = self.pre_head_dropout((lstm_out * attn_w).sum(dim=1))  # [B,512]
        return self.head_binary(pooled), self.head_outcome(pooled), self.head_type(pooled)

class MultiTaskLoss(nn.Module):
    def __init__(self, n_tasks=3):
        super().__init__()
        self.log_vars = nn.Parameter(torch.zeros(n_tasks))
    def forward(self, losses, active_masks):
        total = 0.0
        for i, (l, active) in enumerate(zip(losses, active_masks)):
            if active:
                total = total + torch.exp(-self.log_vars[i]) * l + self.log_vars[i]
        return total

# ---------- DATA LOADING ----------
# TABULAR FEATURES (10-dim, PER HOP, cumulative up to hop t — no future leakage):
#   1 step_count  2 total_tool_calls  3 mutating_action_ratio
#   4 hallucinated_tool (this hop)  5 avg_tool_args_count  6 repetitive_call_ratio
#   7 tool_chain_length (this hop)  8 tool_call_density
#   9 this_hop_text_length  10 max_tool_arg_depth (this hop)
# Features 4,7,9,10 are naturally per-hop. The rest MUST use only hops <= t.

def build_tabular_vector(hops_so_far, current_hop, env_schema):
    calls = [h for h in hops_so_far if h.get("tool_name")]
    n_calls = len(calls)
    mutating = sum(1 for h in calls if env_schema.get(h["tool_name"], {}).get("is_mutating", False))
    seen, repeats = set(), 0
    for h in calls:
        key = (h["tool_name"], json.dumps(h.get("tool_args", {}), sort_keys=True))
        if key in seen: repeats += 1
        seen.add(key)
    chain = 0
    for h in reversed(hops_so_far):
        if h.get("tool_name"): chain += 1
        else: break
    def depth(o, d=0):
        return max((depth(v, d+1) for v in o.values()), default=d) if isinstance(o, dict) and o else d
    return np.array([
        len(hops_so_far), n_calls,
        mutating / n_calls if n_calls else 0.0,
        1.0 if current_hop.get("tool_name") and current_hop["tool_name"] not in env_schema else 0.0,
        np.mean([len(h.get("tool_args", {})) for h in calls]) if calls else 0.0,
        repeats / n_calls if n_calls else 0.0,
        chain,
        n_calls / len(hops_so_far) if hops_so_far else 0.0,
        len(current_hop.get("text", "")),
        depth(current_hop.get("tool_args", {})),
    ], dtype=np.float32)

def load_dataset():
    runs = pd.read_csv(CSV_PATH)
    events = pd.read_csv(EVENTS_PATH)
    
    # ── Handle nulls & clean ──
    events["tool_called"] = events["tool_called"].fillna("")
    events["tool_args"] = events["tool_args"].fillna("{}")
    events["output_text"] = events["output_text"].fillna("")
    runs["injection_type"] = runs["injection_type"].fillna("")
    runs["injection_outcome"] = runs["injection_outcome"].fillna("clean")
    
    # ── Map Labels ──
    OUTCOME_MAP = {"clean": 0, "partial": 1, "ignored": 2, "full_success": 3}
    TYPE_MAP = {
        "direct_injection": 0,
        "indirect_injection": 1,
        "memory_poisoning": 2,
        "tool_misuse": 3,
        "dos": 4
    }
    
    print("Loading SentenceTransformer (all-MiniLM-L6-v2)...")
    embedder = SentenceTransformer('all-MiniLM-L6-v2', device=DEVICE)
    
    # ── Drop traces without exactly 3 hops ──
    event_counts = events.groupby("run_id").size()
    valid_runs = event_counts[event_counts == 3].index
    runs = runs[runs["run_id"].isin(valid_runs)].copy()
    
    events = events[events["run_id"].isin(runs["run_id"])].sort_values(["run_id", "hop_index"])
    
    print(f"Processing {len(runs)} complete multi-suite runs...")
    
    X_text_list, X_tab_list = [], []
    y_bin, y_out, y_type, groups, suites = [], [], [], [], []
    runs_indexed = runs.set_index("run_id")
    env_schema = {} # Dummy schema to fulfill argument
    
    for rid, hop_df in events.groupby("run_id", sort=False):
        if len(hop_df) != 3: continue
        
        run_data = runs_indexed.loc[rid]
        run_data = runs_indexed.loc[rid]
        type_str = str(run_data["injection_type"])
        out_str = str(run_data["injection_outcome"])
        suite = str(run_data["environment_domain"])
        
        is_attack = type_str != ""
        y_bin.append(1 if is_attack else 0)
        y_out.append(OUTCOME_MAP.get(out_str, 0))
        y_type.append(TYPE_MAP.get(type_str, -1) if is_attack else -1)
        groups.append(rid)
        suites.append(suite)
        
        hops, hop_texts, hop_tabs = [], [], []
        
        for i in range(3):
            row = hop_df.iloc[i]
            text_val = str(row["output_text"])
            hop_texts.append(text_val)
            
            try:
                args_parsed = json.loads(row["tool_args"])
            except:
                args_parsed = {}
                
            hop_dict = {
                "tool_name": row["tool_called"] if row["tool_called"] else None,
                "tool_args": args_parsed,
                "tool_error": False,
                "tool_response": "", 
                "text": text_val
            }
            hops.append(hop_dict)
            
            # CAUSALITY FIX: build_tabular_vector ONLY sees hops up to and including current
            hop_tabs.append(build_tabular_vector(hops[:i+1], hops[i], env_schema))
            
        X_tab_list.append(np.stack(hop_tabs))
        X_text_list.append(embedder.encode(hop_texts))

    X_text = np.stack(X_text_list)
    X_tab = np.stack(X_tab_list)
    y_bin, y_out, y_type, groups, suites = map(np.array, [y_bin, y_out, y_type, groups, suites])
    
    strat_labels = [f"{b}_{o}_{t}_{s}" for b,o,t,s in zip(y_bin, y_out, y_type, suites)]
    
    return X_text, X_tab, y_bin, y_out, y_type, groups, strat_labels, suites

# ---------- TRAIN + EVAL ONE SEED ----------
def run_seed(seed, X_text, X_tab, y_bin, y_out, y_type, groups, strat_labels, suites):
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    train_idx, test_idx = next(sgkf.split(X_text, strat_labels, groups))
    # further split train_idx -> train/val (e.g. 85/15) for threshold selection
    n_val = max(1, int(0.15 * len(train_idx)))
    rng = np.random.RandomState(seed)
    perm = rng.permutation(train_idx)
    val_idx, tr_idx = perm[:n_val], perm[n_val:]

    model = ReconMindModel(tab_dim=TABULAR_DIM).to(DEVICE)
    mt_loss = MultiTaskLoss().to(DEVICE)
    opt = torch.optim.AdamW(list(model.parameters()) + list(mt_loss.parameters()),
                             lr=3e-4, weight_decay=1e-4)

    # Calculate sampling weights based on (suite, y_bin) to balance batches
    tr_suites = suites[tr_idx]
    tr_y = y_bin[tr_idx]
    tr_keys = [f"{s}_{y}" for s, y in zip(tr_suites, tr_y)]
    from collections import Counter
    counts = Counter(tr_keys)
    weight_map = {k: len(tr_idx) / (len(counts) * c) for k, c in counts.items()}
    sample_weights = np.array([weight_map[k] for k in tr_keys])

    # Class weights for loss functions (already implemented for outcome/type)
    ce_bin = torch.nn.CrossEntropyLoss()
    ce_out = torch.nn.CrossEntropyLoss(weight=class_weights(y_out[tr_idx]))
    type_mask = y_type[tr_idx] != -1
    ce_type = torch.nn.CrossEntropyLoss(ignore_index=-1,
                weight=class_weights(y_type[tr_idx][type_mask]) if type_mask.any() else None)

    for epoch in range(30):
        model.train()
        for i in batches(tr_idx, bs=16, seed=seed, epoch=epoch, sample_weights=sample_weights):
            xb_text = torch.tensor(X_text[i]).float().to(DEVICE)
            xb_tab  = torch.tensor(X_tab[i]).float().to(DEVICE)
            yb_bin  = torch.tensor(y_bin[i]).long().to(DEVICE)
            yb_out  = torch.tensor(y_out[i]).long().to(DEVICE)
            yb_type = torch.tensor(y_type[i]).long().to(DEVICE)

            logit_b, logit_o, logit_t = model(xb_text, xb_tab)
            loss_b = ce_bin(logit_b, yb_bin)
            loss_o = ce_out(logit_o, yb_out)
            active_type = (yb_type != -1).any().item()
            loss_t = ce_type(logit_t, yb_type) if active_type else torch.tensor(0.0, device=DEVICE)

            loss = mt_loss([loss_b, loss_o, loss_t], [True, True, active_type])
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()

    # ---- threshold: select on val, apply to test ----
    val_probs = predict_probs(model, X_text[val_idx], X_tab[val_idx])
    best_t, best_f1 = 0.5, 0.0
    for t in np.arange(0.01, 0.99, 0.01):
        f1 = f1_score(y_bin[val_idx], (val_probs >= t).astype(int))
        if f1 > best_f1: best_f1, best_t = f1, t

    test_probs = predict_probs(model, X_text[test_idx], X_tab[test_idx])
    test_pred = (test_probs >= best_t).astype(int)
    bin_f1 = f1_score(y_bin[test_idx], test_pred)
    bin_auc = roc_auc_score(y_bin[test_idx], test_probs) if len(set(y_bin[test_idx])) > 1 else 0.0
    type_f1 = evaluate_type_head(model, X_text[test_idx], X_tab[test_idx], y_type[test_idx])

    print(f"\n--- Seed {seed} Test Results ---")
    print(f"Overall Binary F1: {bin_f1:.4f} | AUC: {bin_auc:.4f} | Global Threshold: {best_t:.2f}")
    for s in np.unique(suites[test_idx]):
        mask = suites[test_idx] == s
        if sum(mask) > 0:
            f1 = f1_score(y_bin[test_idx][mask], test_pred[mask], zero_division=0)
            acc = (y_bin[test_idx][mask] == test_pred[mask]).mean()
            atk_ratio = y_bin[test_idx][mask].mean()
            print(f"  {s.ljust(10)}: F1={f1:.4f} | Acc={acc:.4f} | N={sum(mask):<3} (Attack Ratio: {atk_ratio:.2f})")
            
            if s != "workspace" and seed == 42:
                print(f"    [Raw Probs] {s}: {np.round(test_probs[mask], 3)}")
                print(f"    [True Lbls] {s}: {y_bin[test_idx][mask]}")

    return {"seed": seed, "threshold": best_t, "bin_f1": bin_f1, "bin_auc": bin_auc, "type_f1": type_f1}

# ---------- helpers (implement per your existing code) ----------
def class_weights(y):
    y = np.array(y)
    classes = np.unique(y)
    weights = np.zeros(y.max() + 1, dtype=np.float32)
    for c in classes:
        weights[c] = len(y) / (len(classes) * np.sum(y == c) + 1e-6)
    return torch.tensor(weights, dtype=torch.float32).to(DEVICE)

def batches(idx, bs, seed, epoch, sample_weights=None):
    rng = np.random.RandomState(seed + epoch)
    if sample_weights is not None:
        p = sample_weights / sample_weights.sum()
        perm = rng.choice(idx, size=len(idx), replace=True, p=p)
    else:
        perm = rng.permutation(idx)
    for i in range(0, len(perm), bs):
        yield perm[i : i + bs]

def predict_probs(model, X_text, X_tab):
    model.eval()
    probs = []
    with torch.no_grad():
        for i in range(0, len(X_text), 64):
            te = torch.tensor(X_text[i:i+64]).float().to(DEVICE)
            ta = torch.tensor(X_tab[i:i+64]).float().to(DEVICE)
            logit_b, _, _ = model(te, ta)
            probs.append(torch.softmax(logit_b, dim=1)[:, 1].cpu().numpy())
    return np.concatenate(probs) if probs else np.array([])

def evaluate_type_head(model, X_text, X_tab, y_type):
    model.eval()
    mask = y_type != -1
    if not mask.any():
        return 0.0
    preds = []
    with torch.no_grad():
        for i in range(0, len(X_text), 64):
            te = torch.tensor(X_text[i:i+64]).float().to(DEVICE)
            ta = torch.tensor(X_tab[i:i+64]).float().to(DEVICE)
            _, _, logit_t = model(te, ta)
            preds.append(logit_t.argmax(dim=1).cpu().numpy())
    preds = np.concatenate(preds)
    from sklearn.metrics import f1_score
    return f1_score(y_type[mask], preds[mask], average="macro")

# ---------- MAIN ----------
if __name__ == "__main__":
    data = load_dataset()
    
    # ── CAUSALITY SANITY CHECK ──
    print("\n--- SANITY CHECK: TABULAR CAUSALITY ---")
    X_tab = data[1] # Unpacking: (X_text, X_tab, y_bin, y_out, y_type, groups, strat_labels)
    for i in range(min(10, len(X_tab))):
        t = X_tab[i]
        assert t[2][0] >= t[1][0] >= t[0][0], f"FATAL Trace {i}: Step count is not monotonically increasing!"
        assert not np.array_equal(t[0], t[2]), f"FATAL Trace {i}: Hop 0 and Hop 2 tabular features are identical (Leakage detected)!"
    print(f"Sanity check passed for first {min(10, len(X_tab))} traces! Temporal causality is intact.\n")
    print("---------------------------------------\n")
    results = [run_seed(s, *data) for s in SEEDS]

    bin_f1s = [r["bin_f1"] for r in results]
    print(f"Binary F1: {np.mean(bin_f1s):.4f} ± {np.std(bin_f1s):.4f} "
          f"(min={min(bin_f1s):.4f}, max={max(bin_f1s):.4f})")
    with open("phase2_results.json", "w") as f:
        json.dump(results, f, indent=2)