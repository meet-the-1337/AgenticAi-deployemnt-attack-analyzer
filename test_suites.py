import torch
import numpy as np
import pandas as pd
from train_phase2 import load_dataset, ReconMindModel, DEVICE
from sklearn.metrics import f1_score

def evaluate_suites():
    print("Loading dataset...")
    X_text, X_tab, y_bin, y_out, y_type, groups, strat_labels = load_dataset()
    
    runs = pd.read_csv("dataset/agentdojo_local_runs.csv")
    events = pd.read_csv("dataset/agentdojo_local_events.csv")
    
    event_counts = events.groupby("run_id").size()
    valid_runs = event_counts[event_counts == 3].index
    runs = runs[runs["run_id"].isin(valid_runs)]
    
    print("\nLoading model...")
    ckpt = torch.load("models/deep/best_model.pt", map_location=DEVICE, weights_only=False)
    
    # We must instantiate the model. The CFG defaults to TABULAR_DIM=10 in the class
    # wait, ReconMindModel in train_phase2.py has a default tab_dim=10 now.
    model = ReconMindModel(tab_dim=10).to(DEVICE)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    
    print("\nRunning inference...")
    y_pred = []
    y_true = []
    suites = []
    
    runs_indexed = runs.set_index("run_id")
    
    with torch.no_grad():
        for i in range(len(groups)):
            rid = groups[i]
            suite = runs_indexed.loc[rid]["environment_domain"]
            suites.append(suite)
            
            xb_text = torch.tensor(X_text[i:i+1]).float().to(DEVICE)
            xb_tab  = torch.tensor(X_tab[i:i+1]).float().to(DEVICE)
            
            logit_b, _, _ = model(xb_text, xb_tab)
            pred = logit_b.argmax(1).item()
            
            y_pred.append(pred)
            y_true.append(y_bin[i])
            
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    suites = np.array(suites)
    
    print("\n--- Per-Suite F1 Score (Full Dataset) ---")
    for s in np.unique(suites):
        mask = suites == s
        f1 = f1_score(y_true[mask], y_pred[mask], zero_division=0)
        acc = (y_true[mask] == y_pred[mask]).mean()
        print(f"{s.ljust(10)} | N={str(sum(mask)).ljust(4)} | F1: {f1:.4f} | Acc: {acc:.4f} | Attack Ratio: {y_true[mask].mean():.2f}")

if __name__ == "__main__":
    evaluate_suites()
