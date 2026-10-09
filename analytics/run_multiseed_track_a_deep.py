#!/usr/bin/env python3
"""
Track A (Synthetic Data) Multiseed Evaluation
"""
import sys
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score, roc_auc_score

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.deep_model import ReconMindSample, build_tabular_vector, extract_text_pair, OUTCOME_MAP, TYPE_MAP, load_samples
from analytics.run_multiseed_agentdojo import run_single_seed, find_optimal_threshold, evaluate_with_threshold
from analytics.deep_model import TrainConfig, embed_texts

def main():
    print("Loading datasets...")
    samples, texts = load_samples(Path("dataset"))
    print("Embedding texts...")
    embeddings = embed_texts(texts, "sentence-transformers/all-MiniLM-L6-v2", "cuda" if torch.cuda.is_available() else "cpu", Path("models/deep/text_embeddings.npy"))
    
    cfg = TrainConfig(epochs=40, batch_size=32)
    seeds = [42, 123, 7, 99, 2024]
    all_results = []
    
    for s in seeds:
        res = run_single_seed(s, samples, embeddings, cfg)
        print(f"  Seed {s} -> Bin F1: {res['binary_f1']:.4f}")
        all_results.append(res)
        
    bin_f1s = [r["binary_f1"] for r in all_results]
    bin_aucs = [r["binary_auc"] for r in all_results]
    print("=======================")
    print(f"Track A (Synthetic) Bin F1: {np.mean(bin_f1s):.4f} ± {np.std(bin_f1s):.4f}")
    print(f"Track A (Synthetic) AUC: {np.mean(bin_aucs):.4f} ± {np.std(bin_aucs):.4f}")

if __name__ == "__main__":
    main()
