#!/usr/bin/env bash
# scripts/run_full_agentdojo.sh
# =====================================
# Full attack-trace generation on ALL SUITES with AUTO-WATCHDOG.
# Designed for cloud GPU execution.

set -euo pipefail

VENV=".venv/bin/python"
BENCHMARK="-m agentdojo.scripts.benchmark"
LOGDIR_BASE="data/agentdojo_runs_full"

# All environments in AgentDojo
SUITES="-s workspace -s banking -s travel -s slack"

# Adjust model ID based on what you pulled in Ollama on the cloud GPU
export LOCAL_LLM_PORT=11434
export AGENTDOJO_TEMPERATURE=0.7
MODEL_FLAGS="--model LOCAL --model-id qwen2.5:7b" # Change to llama3:8b or your preferred model

# The main attack vectors we want to generate
ATTACKS=("direct" "important_instructions" "dos" "injecagent")

echo "=================================================="
echo " ReconMind Full Dataset Generation (Cloud GPU)"
echo " Target Suites: workspace, banking, travel, slack"
echo " Attacks: ${ATTACKS[*]}"
echo "=================================================="

for attack in "${ATTACKS[@]}"; do
    logdir="${LOGDIR_BASE}/${attack}"
    echo "Starting full run for attack: '${attack}' -> ${logdir}"
    
    mkdir -p "${logdir}"
    
    while true; do
        # We DO NOT delete the folder so that AgentDojo can resume (since --force-rerun is false by default)
        $VENV $BENCHMARK $SUITES --attack "${attack}" $MODEL_FLAGS --logdir "${logdir}" >> "${logdir}/run.log" 2>&1 &
        pid=$!
        
        hang_time=0
        last_count=$(find "${logdir}" -name "*.json" 2>/dev/null | wc -l)
        success=0
        
        while kill -0 $pid 2>/dev/null; do
            sleep 20
            current_count=$(find "${logdir}" -name "*.json" 2>/dev/null | wc -l)
            
            if [ "$current_count" -gt "$last_count" ]; then
                last_count=$current_count
                hang_time=0
            else
                hang_time=$((hang_time + 20))
                if [ $hang_time -ge 180 ]; then
                    echo "  [!] HANG DETECTED (180s no progress at $current_count traces). Restarting to resume..."
                    kill -9 $pid 2>/dev/null || true
                    pkill -9 -f "agentdojo.scripts.benchmark" 2>/dev/null || true
                    sleep 3
                    break
                fi
            fi
        done
        
        # If the process exited normally (not killed by watchdog)
        if ! kill -0 $pid 2>/dev/null && [ $hang_time -lt 180 ]; then
            echo "  → Completed attack '${attack}'. Total traces: ${last_count}"
            break
        fi
    done
done

echo "=================================================="
TOTAL=$(find ${LOGDIR_BASE} -name "*.json" | wc -l)
echo " Generation complete! Total JSON traces: ${TOTAL}"
echo " Now run: .venv/bin/python scripts/extract_agentdojo.py --logdir ${LOGDIR_BASE} --out-dir dataset --prefix agentdojo_full"
echo "=================================================="
