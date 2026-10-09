#!/usr/bin/env bash
# scripts/run_agentdojo_attack_boost.sh
# =====================================
# Targeted attack-trace generation on BANKING SUITE ONLY with AUTO-WATCHDOG.
# Now with timeout + max_tokens patches applied to agentdojo — hangs should
# resolve in ~90s instead of blocking forever.

set -euo pipefail

VENV=".venv/bin/python"
BENCHMARK="-m agentdojo.scripts.benchmark"
LOGDIR_BASE="data/agentdojo_runs_banking_only"
SUITES="-s banking"

export LOCAL_LLM_PORT=11434
export AGENTDOJO_TEMPERATURE=0.7
MODEL_FLAGS="--model LOCAL --model-id qwen3:8b"

ATTACKS=("direct" "important_instructions" "dos")
NUM_RUNS=2

echo "=================================================="
echo " ReconMind Attack-Trace Boost (Banking Suite ONLY)"
echo " Target: ${NUM_RUNS} runs for each attack type"
echo " Anti-Hang: timeout=90s + max_tokens=2048"
echo "=================================================="

run_with_watchdog() {
    local attack=$1
    local run_num=$2
    local logdir="${LOGDIR_BASE}/attack_boost_${attack}_t07_${run_num}"
    
    # Skip if already completed
    local existing=$(find "${logdir}" -name "*.json" 2>/dev/null | wc -l)
    if [ "$existing" -ge 16 ]; then
        echo "[${run_num}/${NUM_RUNS}] Attack '${attack}' run #${run_num} → ALREADY DONE (${existing} traces). Skipping."
        return 0
    fi
    
    while true; do
        rm -rf "${logdir}"
        mkdir -p "${logdir}"
        echo "[${run_num}/${NUM_RUNS}] Attack '${attack}' run #${run_num} → ${logdir} (Starting...)"
        
        $VENV $BENCHMARK $SUITES --attack "${attack}" $MODEL_FLAGS --logdir "${logdir}" > "${logdir}/run.log" 2>&1 &
        local pid=$!
        
        local hang_time=0
        local last_count=0
        local success=0
        
        while kill -0 $pid 2>/dev/null; do
            sleep 10
            local current_count=$(find "${logdir}" -name "*.json" 2>/dev/null | wc -l)
            
            if [ "$current_count" -ge 16 ]; then
                echo "  → Successfully generated ${current_count} traces!"
                kill -9 $pid 2>/dev/null || true
                success=1
                break
            fi
            
            if [ "$current_count" -gt "$last_count" ]; then
                last_count=$current_count
                hang_time=0
            else
                hang_time=$((hang_time + 10))
                if [ $hang_time -ge 120 ]; then
                    echo "  [!] HANG DETECTED (120s no progress at $current_count traces). Restarting..."
                    kill -9 $pid 2>/dev/null || true
                    pkill -9 -f "agentdojo.scripts.benchmark" 2>/dev/null || true
                    sleep 2
                    break
                fi
            fi
        done
        
        if [ "$success" -eq 1 ]; then
            break
        fi
    done
}

for attack in "${ATTACKS[@]}"; do
    for i in $(seq 1 ${NUM_RUNS}); do
        run_with_watchdog "$attack" $i
    done
done

TOTAL=$(find ${LOGDIR_BASE} -name "*.json" -path "*/attack_boost*" | wc -l)
echo "=================================================="
echo " Attack boost complete!"
echo " Total attack traces generated: ${TOTAL}"
echo "=================================================="
