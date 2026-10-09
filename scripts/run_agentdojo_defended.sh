#!/usr/bin/env bash
# scripts/run_agentdojo_defended.sh
# ==============================================================
# Generates a highly valuable "Defended" dataset. 
# We run the attacks against AgentDojo's built-in defenses 
# to ensure our model can detect attacks that try to bypass them!

set -euo pipefail

VENV=".venv/bin/python"
BENCHMARK="-m agentdojo.scripts.benchmark"
LOGDIR="data/agentdojo_runs_defended"
SUITES="-s banking -s travel"
MODEL_FLAGS="--model LOCAL --model-id qwen3:8b"

echo "=================================================="
echo " ReconMind Defended Campaign (Banking & Travel)"
echo "=================================================="

mkdir -p "${LOGDIR}"

# 1. Defense: Transformers PI Detector (Local)
echo ">>> Running with Defense: transformers_pi_detector"
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --attack direct --defense transformers_pi_detector --logdir "${LOGDIR}/pi_detector" 2>&1 | tail -2

# 2. Defense: Spotlighting
echo ">>> Running with Defense: spotlighting_with_delimiting"
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --attack important_instructions --defense spotlighting_with_delimiting --logdir "${LOGDIR}/spotlighting" 2>&1 | tail -2

# 3. Defense: Repeat User Prompt
echo ">>> Running with Defense: repeat_user_prompt"
$VENV $BENCHMARK $SUITES $MODEL_FLAGS --attack dos --defense repeat_user_prompt --logdir "${LOGDIR}/repeat_prompt" 2>&1 | tail -2

echo "=================================================="
echo " Defended Campaign complete!"
echo " Extract using:"
echo " .venv/bin/python scripts/extract_agentdojo.py --logdir ${LOGDIR} --out-dir dataset --prefix agentdojo_defended"
