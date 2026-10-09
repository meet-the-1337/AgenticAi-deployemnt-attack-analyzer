#!/usr/bin/env bash
# scripts/run_agentdojo_campaign.sh
# ==================================
# Runs the full AgentDojo benchmark campaign to generate training data.
#
# What this script does:
#   1. Clean runs (no attack) → label: injection_outcome=clean
#   2. Direct injection runs  → label: injection_type=direct_injection
#   3. Indirect injection runs (important_instructions) → indirect_injection
#   4. Tool misuse / DoS runs → tool_misuse
#   5. Defended runs (with tool_filter defense) → defense_triggered=1
#
# Usage:
#   chmod +x scripts/run_agentdojo_campaign.sh
#   ./scripts/run_agentdojo_campaign.sh
#
# Prerequisites:
#   - .venv with agentdojo installed
#   - OPENAI_API_KEY set (for gpt-3.5-turbo), OR use --model LOCAL with ollama
#   - For local/free runs: use LOCAL model (points to Ollama qwen3:8b)
#
# Cost estimate with gpt-3.5-turbo:  ~$10-15 for all runs
# Cost with LOCAL (Ollama qwen3:8b): $0 — but slower

set -euo pipefail

VENV=".venv/bin/python"
BENCHMARK="-m agentdojo.scripts.benchmark"
LOGDIR="data/agentdojo_runs"
# Running the full workspace suite to generate ~150-200 runs
SUITES="-s workspace"

# ── API Keys ──────────────────────────────────────────────────────────
export GROQ_API_KEY="gsk_YOUR_KEY_HERE" # REDACTED for security

# ── Model selection ───────────────────────────────────────────────────
export LOCAL_LLM_PORT=11434
MODEL="LOCAL"
MODEL_ID="qwen3:8b"

if [ "$MODEL" = "LOCAL" ]; then
    MODEL_FLAGS="--model LOCAL --model-id ${MODEL_ID}"
else
    MODEL_FLAGS="--model ${MODEL}"
fi

echo "=================================================="
echo " ReconMind x AgentDojo Training Campaign"
echo " Model: ${MODEL} ${MODEL_ID:-}"
echo " Log directory: ${LOGDIR}"
echo "=================================================="
echo ""

mkdir -p "${LOGDIR}"

# ── Run 1: Clean (no attack) ──────────────────────────────────────────
echo "[1/5] Clean runs (no attack)..."
$VENV $BENCHMARK \
    $SUITES \
    $MODEL_FLAGS \
    --logdir "${LOGDIR}/clean" \
    2>&1 | tail -5
echo "    Done."

# ── Run 2: Direct injection ───────────────────────────────────────────
echo "[2/5] Direct injection attacks..."
$VENV $BENCHMARK \
    $SUITES \
    $MODEL_FLAGS \
    --attack direct \
    --logdir "${LOGDIR}/direct" \
    2>&1 | tail -5

$VENV $BENCHMARK \
    $SUITES \
    $MODEL_FLAGS \
    --attack ignore_previous \
    --logdir "${LOGDIR}/ignore_previous" \
    2>&1 | tail -5
echo "    Done."

# ── Run 3: Indirect injection (important_instructions) ───────────────
echo "[3/5] Indirect injection attacks..."
$VENV $BENCHMARK \
    $SUITES \
    $MODEL_FLAGS \
    --attack important_instructions \
    --logdir "${LOGDIR}/important_instructions" \
    2>&1 | tail -5

$VENV $BENCHMARK \
    $SUITES \
    $MODEL_FLAGS \
    --attack injecagent \
    --logdir "${LOGDIR}/injecagent" \
    2>&1 | tail -5
echo "    Done."

# ── Run 4: Tool misuse / DoS ──────────────────────────────────────────
echo "[4/5] Tool misuse / DoS attacks..."
$VENV $BENCHMARK \
    $SUITES \
    $MODEL_FLAGS \
    --attack dos \
    --logdir "${LOGDIR}/dos" \
    2>&1 | tail -5

$VENV $BENCHMARK \
    $SUITES \
    $MODEL_FLAGS \
    --attack tool_knowledge \
    --logdir "${LOGDIR}/tool_knowledge" \
    2>&1 | tail -5
echo "    Done."

# ── Run 5: With defense active (tool_filter) ─────────────────────────
echo "[5/5] Defended runs (tool_filter defense)..."
$VENV $BENCHMARK \
    $SUITES \
    $MODEL_FLAGS \
    --attack important_instructions \
    --defense tool_filter \
    --logdir "${LOGDIR}/defended_tool_filter" \
    2>&1 | tail -5

$VENV $BENCHMARK \
    $SUITES \
    $MODEL_FLAGS \
    --attack direct \
    --defense spotlighting_with_delimiting \
    --logdir "${LOGDIR}/defended_spotlighting" \
    2>&1 | tail -5
echo "    Done."

echo ""
echo "=================================================="
echo " Campaign complete! Logs saved to: ${LOGDIR}"
echo ""
echo " Next step — extract logs to CSV:"
echo "   .venv/bin/python scripts/extract_agentdojo.py \\"
echo "     --logdir ${LOGDIR} \\"
echo "     --out-dir dataset \\"
echo "     --prefix agentdojo"
echo ""
echo " Then merge with existing data:"
echo "   .venv/bin/python scripts/merge_datasets.py"
echo ""
echo " Then retrain:"
echo "   .venv/bin/python analytics/train_model.py \\"
echo "     --dataset-dir dataset/merged \\"
echo "     --epochs 80 --no-cache"
echo "=================================================="
