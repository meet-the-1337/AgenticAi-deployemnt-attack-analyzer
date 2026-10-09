#!/usr/bin/env bash
# scripts/run_agentdojo_workspace_resume.sh
# ==============================================================
# Resumes the massive 'workspace' campaign. 
# We already have 427 direct_injections, so this script targets
# indirect, dos, and clean to perfectly balance the workspace dataset.
# It will run until you kill it or it finishes.

set -euo pipefail

VENV=".venv/bin/python"
BENCHMARK="-m agentdojo.scripts.benchmark"
LOGDIR="data/agentdojo_runs" # Using original logdir where the 427 direct runs live
SUITES="-s workspace"
MODEL_FLAGS="--model LOCAL --model-id qwen3:8b"

echo "=================================================="
echo " ReconMind Massive Campaign (Workspace Suite)"
echo "=================================================="

# 1. Indirect Injection
echo ">>> Generating indirect_injection..."
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --attack important_instructions --logdir "${LOGDIR}/important_instructions" 2>&1 | tail -2

# 2. Tool Misuse / DoS
echo ">>> Generating tool_misuse (dos)..."
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --attack dos --logdir "${LOGDIR}/dos" 2>&1 | tail -2

# 3. Clean
echo ">>> Generating clean..."
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --logdir "${LOGDIR}/clean" 2>&1 | tail -2

echo "=================================================="
echo " Workspace Campaign complete!"
echo " Extract using:"
echo " .venv/bin/python scripts/extract_agentdojo.py --logdir ${LOGDIR} --out-dir dataset --prefix agentdojo_workspace"
