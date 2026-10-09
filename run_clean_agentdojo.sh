#!/usr/bin/env bash
set -euo pipefail

VENV=".venv/bin/python"
BENCHMARK="-m agentdojo.scripts.benchmark"
LOGDIR="data/agentdojo_runs_local/clean"

# Target ONLY the minority suites for the clean baseline
SUITES="-s banking -s travel -s slack"
export LOCAL_LLM_PORT=11434
export AGENTDOJO_TEMPERATURE=0.7
MODEL_FLAGS="--model LOCAL --model-id qwen3:8b" 

echo "=================================================="
echo " Generating Clean Baselines (No Attacks)"
echo " Suites: banking, travel, slack"
echo "=================================================="

mkdir -p "${LOGDIR}"

$VENV $BENCHMARK $SUITES $MODEL_FLAGS --logdir "${LOGDIR}" > "${LOGDIR}/run.log" 2>&1 &
pid=$!

hang_time=0
last_count=$(find "${LOGDIR}" -name "*.json" 2>/dev/null | wc -l)

while kill -0 $pid 2>/dev/null; do
    sleep 20
    current_count=$(find "${LOGDIR}" -name "*.json" 2>/dev/null | wc -l)
    
    if [ "$current_count" -gt "$last_count" ]; then
        last_count=$current_count
        hang_time=0
    else
        hang_time=$((hang_time + 20))
        if [ $hang_time -ge 120 ]; then
            echo "  [!] HANG DETECTED (120s no progress at $current_count traces)."
            kill -9 $pid 2>/dev/null || true
            pkill -9 -f "agentdojo.scripts.benchmark" 2>/dev/null || true
            break
        fi
    fi
done

echo "=================================================="
echo " Generation complete! Extracted clean traces: ${last_count}"
echo " Re-building final CSV dataset..."
$VENV scripts/extract_agentdojo.py --logdir data/agentdojo_runs_local --out-dir dataset --prefix agentdojo_local
echo "=================================================="
