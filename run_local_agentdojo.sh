#!/usr/bin/env bash
# scripts/run_local_agentdojo.sh
# =====================================
# Full attack-trace generation for LOCAL PC
# =====================================

set -euo pipefail

VENV=".venv/bin/python"
BENCHMARK="-m agentdojo.scripts.benchmark"
LOGDIR_BASE="data/agentdojo_runs_local"

# All environments in AgentDojo
SUITES="-s workspace -s banking -s travel -s slack"

# Use standard local ollama port and local model
export LOCAL_LLM_PORT=11434
export AGENTDOJO_TEMPERATURE=0.7
MODEL_FLAGS="--model LOCAL --model-id qwen3:8b" 

# The main attack vectors we want to generate
ATTACKS=("direct" "important_instructions" "dos" "injecagent")

echo "=================================================="
echo " ReconMind Dataset Generation (Local GPU)"
echo " Target Suites: workspace, banking, travel, slack"
echo " Attacks: ${ATTACKS[*]}"
echo "=================================================="

# Optional: Set max performance for NVIDIA GPU
sudo nvidia-smi -pm 1 || true

FAILED_ATTACKS=()

run_attack() {
    local attack=$1
    local logdir="${LOGDIR_BASE}/${attack}"
    echo "Starting run for attack: '${attack}' -> ${logdir}"
    
    mkdir -p "${logdir}"
    
    $VENV $BENCHMARK $SUITES --attack "${attack}" $MODEL_FLAGS --logdir "${logdir}" >> "${logdir}/run.log" 2>&1 &
    local pid=$!
    
    local hang_time=0
    local last_count=$(find "${logdir}" -name "*.json" 2>/dev/null | wc -l)
    
    while kill -0 $pid 2>/dev/null; do
        sleep 20
        local current_count=$(find "${logdir}" -name "*.json" 2>/dev/null | wc -l)
        
        if [ "$current_count" -gt "$last_count" ]; then
            last_count=$current_count
            hang_time=0
        else
            hang_time=$((hang_time + 20))
            if [ $hang_time -ge 180 ]; then
                echo "  [!] HANG DETECTED for '${attack}' (180s no progress at $current_count traces)."
                kill -9 $pid 2>/dev/null || true
                pkill -9 -f "agentdojo.scripts.benchmark" 2>/dev/null || true
                sleep 3
                return 1 # Return 1 to indicate it failed/stopped
            fi
        fi
    done
    
    echo "  → Completed attack '${attack}'. Total traces: ${last_count}"
    return 0
}

for attack in "${ATTACKS[@]}"; do
    if ! run_attack "$attack"; then
        echo "  [!] Skipping '${attack}' for now. Added to retry queue."
        FAILED_ATTACKS+=("$attack")
    fi
done

if [ ${#FAILED_ATTACKS[@]} -gt 0 ]; then
    echo "=================================================="
    echo " Retrying stopped attacks: ${FAILED_ATTACKS[*]}"
    echo "=================================================="
    for attack in "${FAILED_ATTACKS[@]}"; do
        if ! run_attack "$attack"; then
            echo "  [!] Attack '${attack}' stopped again on retry. Moving on."
        fi
    done
fi

echo "=================================================="
TOTAL=$(find ${LOGDIR_BASE} -name "*.json" 2>/dev/null | wc -l)
echo " Generation complete! Total JSON traces: ${TOTAL}"
echo " Now extracting CSV..."
$VENV scripts/extract_agentdojo.py --logdir ${LOGDIR_BASE} --out-dir dataset --prefix agentdojo_local
echo "=================================================="
