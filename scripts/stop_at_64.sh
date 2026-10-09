#!/bin/bash
while true; do
    count=$(find data/agentdojo_runs_banking_only -name "*.json" -path "*/clean_boost_t07_*" | wc -l)
    if [ "$count" -ge 64 ]; then
        echo "Count is $count, killing watchdog bash script..."
        pkill -f "run_agentdojo_clean_boost.sh"
        break
    fi
    sleep 5
done
