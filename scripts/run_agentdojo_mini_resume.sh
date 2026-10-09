#!/usr/bin/env bash
set -euo pipefail

VENV=".venv/bin/python"
BENCHMARK="-m agentdojo.scripts.benchmark"
LOGDIR="data/agentdojo_runs_mini"
SUITES="-s banking"
MODEL_FLAGS="--model LOCAL --model-id qwen3:8b"

echo "=================================================="
echo " ReconMind Mini-Campaign (Resuming Steps 3 & 4)"
echo "=================================================="

# 3. Indirect Injection
echo "[3/4] Indirect injection..."
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --attack important_instructions --logdir "${LOGDIR}/important_instructions" 2>&1 | tail -2

# 4. Tool Misuse / DoS
echo "[4/4] Tool misuse / DoS..."
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --attack dos --logdir "${LOGDIR}/dos" 2>&1 | tail -2

echo "=================================================="
echo " Mini-Campaign complete!"
