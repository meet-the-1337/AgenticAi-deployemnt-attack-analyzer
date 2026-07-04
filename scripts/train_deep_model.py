"""
scripts/train_deep_model.py
===========================
CLI entrypoint to train the deep multi-task sequence model.
"""

import argparse
import sys
import os
from pathlib import Path

# Setup sys.path so we can import from top-level folders
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analytics.deep_model import TrainConfig, train

def main():
    parser = argparse.ArgumentParser(description="Train ReconMind Deep Anomaly Classifier")
    parser.add_argument("--epochs", type=int, default=60, help="Number of epochs to train")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for training")
    parser.add_argument("--no-cache", action="store_true", help="Do not load cached SentenceTransformer embeddings")
    parser.add_argument("--output-dir", type=str, default="models/deep", help="Output directory for best model and results")
    
    args = parser.parse_args()
    
    cfg = TrainConfig()
    cfg.epochs = args.epochs
    cfg.batch_size = args.batch_size
    cfg.output_dir = Path(args.output_dir)
    
    # Handle cache bypass
    cache_path = cfg.output_dir / "text_embeddings.npy"
    if args.no_cache and cache_path.exists():
        print(f"Bypassing cache: removing {cache_path}")
        try:
            cache_path.unlink()
        except Exception as e:
            print(f"Warning: could not delete cache file: {e}")
            
    print(f"Starting training: epochs={cfg.epochs}, batch_size={cfg.batch_size}, no_cache={args.no_cache}, output_dir={cfg.output_dir}")
    train(cfg)

if __name__ == "__main__":
    main()
