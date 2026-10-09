echo "Starting FULL workspace campaign..."
./scripts/run_agentdojo_campaign.sh

echo "Extracting..."
.venv/bin/python scripts/extract_agentdojo.py \
  --logdir data/agentdojo_runs \
  --out-dir dataset \
  --prefix agentdojo_full

echo "Merging..."
.venv/bin/python scripts/merge_datasets.py \
  --new-runs dataset/agentdojo_full_runs.csv \
  --new-events dataset/agentdojo_full_events.csv

echo "Training..."
PYTHONPATH=. .venv/bin/python analytics/train_model.py \
  --dataset-dir dataset/merged \
  --epochs 20 \
  --no-cache
