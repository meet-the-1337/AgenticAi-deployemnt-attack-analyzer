#!/usr/bin/env bash
# scripts/run_agentdojo_mini.sh
# ==================================
# A fast "mini-campaign" designed to generate a perfectly balanced dataset 
# in under an hour. By restricting all attack types to the 'banking' suite, 
# we prevent the model from learning suite-specific artifacts (confounding variable).

set -euo pipefail

VENV=".venv/bin/python"
BENCHMARK="-m agentdojo.scripts.benchmark"
LOGDIR="data/agentdojo_runs_mini"

# Using the 'banking' suite because it's much smaller than 'workspace', 
# finishing in ~45 minutes rather than 28 hours.
SUITES="-s banking"

export LOCAL_LLM_PORT=11434
MODEL_FLAGS="--model LOCAL --model-id qwen3:8b"

echo "=================================================="
echo " ReconMind Mini-Campaign (Banking Suite Only)"
echo "=================================================="

mkdir -p "${LOGDIR}"

# 1. Clean
echo "[1/4] Clean runs..."
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --logdir "${LOGDIR}/clean" 2>&1 | tail -2

# 2. Direct Injection
echo "[2/4] Direct injection..."
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --attack direct --logdir "${LOGDIR}/direct" 2>&1 | tail -2

# 3. Indirect Injection
echo "[3/4] Indirect injection..."
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --attack important_instructions --logdir "${LOGDIR}/important_instructions" 2>&1 | tail -2

# 4. Tool Misuse / DoS
echo "[4/4] Tool misuse / DoS..."
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --attack dos --logdir "${LOGDIR}/dos" 2>&1 | tail -2

echo "=================================================="
echo " Mini-Campaign complete!"
echo " Extract using:"
echo " .venv/bin/python scripts/extract_agentdojo.py --logdir ${LOGDIR} --out-dir dataset --prefix agentdojo_mini"
