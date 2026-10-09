#!/usr/bin/env bash
# scripts/monitor_progress.sh
# ==============================================================================
# Live Monitor for ReconMind Dataset Generation
# Run this in your terminal to see real-time progress of the background generator!

LOGDIR="data/agentdojo_runs_defended"
TOTAL_EXPECTED=515 # Calculated based on banking + travel suite sizes

echo -e "\033[1;36m====================================================\033[0m"
echo -e "\033[1;36m   ReconMind Live Dataset Generation Monitor        \033[0m"
echo -e "\033[1;36m====================================================\033[0m"

START_TIME=$(date +%s)
START_COUNT=$(find "$LOGDIR" -type f -name "*.json" 2>/dev/null | wc -l || echo 0)

while true; do
    CURRENT_TIME=$(date +%s)
    CURRENT_COUNT=$(find "$LOGDIR" -type f -name "*.json" 2>/dev/null | wc -l || echo 0)
    
    # Check which step is currently active
    if pgrep -f "transformers_pi_detector" > /dev/null; then
        CURRENT_STEP="[1/3] PI Detector Defense (Direct Injection)"
    elif pgrep -f "spotlighting_with_delimiting" > /dev/null; then
        CURRENT_STEP="[2/3] Spotlighting Defense (Indirect Injection)"
    elif pgrep -f "repeat_user_prompt" > /dev/null; then
        CURRENT_STEP="[3/3] Repeat Prompt Defense (DoS)"
    else
        CURRENT_STEP="Finishing up or stopped..."
    fi

    # Calculate Progress
    PERCENT=$(( CURRENT_COUNT * 100 / TOTAL_EXPECTED ))
    if [ $PERCENT -gt 100 ]; then PERCENT=100; fi

    # Calculate ETA
    ELAPSED=$(( CURRENT_TIME - START_TIME ))
    PRODUCED=$(( CURRENT_COUNT - START_COUNT ))
    
    if [ $PRODUCED -gt 0 ] && [ $ELAPSED -gt 0 ]; then
        FILES_PER_SEC=$(bc -l <<< "$PRODUCED / $ELAPSED")
        REMAINING_FILES=$(( TOTAL_EXPECTED - CURRENT_COUNT ))
        ETA_SEC=$(bc -l <<< "$REMAINING_FILES / $FILES_PER_SEC")
        ETA_MIN=$(bc <<< "$ETA_SEC / 60")
    else
        ETA_MIN="Calculating..."
    fi

    # Print UI
    clear
    echo -e "\033[1;32mActive Process:\033[0m $CURRENT_STEP"
    echo -e "\033[1;33mFiles Generated:\033[0m $CURRENT_COUNT / $TOTAL_EXPECTED ($PERCENT%)"
    
    # Progress Bar
    BAR_FILLED=$(( PERCENT / 2 ))
    BAR_EMPTY=$(( 50 - BAR_FILLED ))
    printf "\033[1;34mProgress:\033[0m ["
    printf "%${BAR_FILLED}s" | tr ' ' '#'
    printf "%${BAR_EMPTY}s" | tr ' ' '-'
    printf "]\n"

    if [[ "$ETA_MIN" != "Calculating..." ]]; then
        echo -e "\033[1;35mEstimated Time Remaining:\033[0m ~$ETA_MIN minutes"
    else
        echo -e "\033[1;35mEstimated Time Remaining:\033[0m Calculating..."
    fi
    
    echo ""
    echo "(Press Ctrl+C to exit monitor. Generation will continue in background)"
    sleep 5
done
