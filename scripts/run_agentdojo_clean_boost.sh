#!/usr/bin/env bash
# scripts/run_agentdojo_clean_boost.sh
# =====================================
# Targeted clean-trace generation on BANKING SUITE ONLY with AUTO-WATCHDOG.
# Fixes the clean-class starvation that caused binary F1 to collapse.
#
# Because the local LLM server hangs periodically, this script monitors
# trace generation. If no new JSON is created in 120 seconds, it kills
# the hanging run and restarts that run from scratch.

set -euo pipefail

VENV=".venv/bin/python"
BENCHMARK="-m agentdojo.scripts.benchmark"
LOGDIR_BASE="data/agentdojo_runs_banking_only"
SUITES="-s banking"

export LOCAL_LLM_PORT=11434
export AGENTDOJO_TEMPERATURE=0.7
MODEL_FLAGS="--model LOCAL --model-id qwen3:8b"

echo "=================================================="
echo " ReconMind Clean-Trace Boost (Banking Suite ONLY)"
echo " Target: 256 new clean traces (16 runs × 16 tasks)"
echo " Includes Anti-Hang Watchdog (TEMP=0.7)"
echo "=================================================="

# Function to run benchmark with a watchdog
run_with_watchdog() {
    local run_num=$1
    local logdir="${LOGDIR_BASE}/clean_boost_t07_${run_num}"
    
    while true; do
        rm -rf "${logdir}"
        mkdir -p "${logdir}"
        echo "[${run_num}/16] Clean run #${run_num} → ${logdir} (Starting...)"
        
        # Start benchmark in background
        $VENV $BENCHMARK $SUITES $MODEL_FLAGS --logdir "${logdir}" > "${logdir}/run.log" 2>&1 &
        local pid=$!
        
        # Watchdog loop
        local hang_time=0
        local last_count=0
        local success=0
        
        while kill -0 $pid 2>/dev/null; do
            sleep 10
            local current_count=$(find "${logdir}" -name "*.json" 2>/dev/null | wc -l)
            
            if [ "$current_count" -eq 16 ]; then
                echo "  → Successfully generated 16 traces!"
                kill -9 $pid 2>/dev/null || true
                success=1
                break
            fi
            
            if [ "$current_count" -gt "$last_count" ]; then
                # Progress was made
                last_count=$current_count
                hang_time=0
            else
                # No progress
                hang_time=$((hang_time + 10))
                if [ $hang_time -ge 120 ]; then
                    echo "  [!] HANG DETECTED (120s no progress at $current_count traces). Killing and restarting run #${run_num}..."
                    kill -9 $pid 2>/dev/null || true
                    pkill -9 -f "agentdojo.scripts.benchmark" 2>/dev/null || true
                    sleep 2
                    break # Break inner loop to trigger outer while loop restart
                fi
            fi
        done
        
        if [ "$success" -eq 1 ]; then
            break # Break outer loop, move to next run
        fi
    done
}

# Start 4 runs with temp=0.7 (Target ~64 traces)
for i in $(seq 1 4); do
    run_with_watchdog $i
done

TOTAL=$(find ${LOGDIR_BASE} -name "*.json" -path "*/clean*" -o -name "*.json" -path "*clean_boost*" | wc -l)
echo "=================================================="
echo " Clean boost complete!"
echo " Total banking clean traces: ${TOTAL}"
echo " Re-extract with:"
echo "   .venv/bin/python scripts/extract_agentdojo.py \\"
echo "     --logdir ${LOGDIR_BASE} --out-dir dataset --prefix agentdojo_banking_only"
echo "=================================================="
