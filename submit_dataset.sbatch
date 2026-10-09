#!/bin/bash
#SBATCH --job-name=agentdojo-gen
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --gres=gpu:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --output=job_output_%j.txt
#SBATCH --error=job_error_%j.txt

echo "===================================="
echo "Job ID        : $SLURM_JOB_ID"
echo "Start Time    : $(date '+%Y-%m-%d %H:%M:%S')"
echo "===================================="

srun --mpi=pmi2 --gres=gpu:1 \
     --container-image=/home/hpc_apps/nvidia+pytorch+25.04-py3.sqsh \
     --container-mounts="$PWD":/workspace \
     --container-workdir=/workspace \
     bash -c '
        set -e # Exit immediately on error

        echo ">>> [1/5] Fixing Package Dependencies & Environment..."
        # Force-fix the aiohappyeyeballs version pinning conflict if present in requirements
        if [ -f "requirements.txt" ]; then
            sed -i "s/aiohappyeyeballs==2.6.1/aiohappyeyeballs==2.6.2/g" requirements.txt
        fi
        
        bash ./setup_env.sh

        echo ">>> [2/5] Downloading and Starting standalone Ollama (No Root)..."
        # Download the official direct binary release to prevent getting an HTML "Not Found" page
	rm -rf ollama
        curl -L https://github.com/ollama/ollama/releases/download/v0.5.7/ollama-linux-amd64 -o ollama
        chmod +x ollama
        
        export OLLAMA_HOST="127.0.0.1:11434"
        export OLLAMA_MODELS="/workspace/ollama_models"
        
        # Start Ollama server in background
        ./ollama serve > ollama.log 2>&1 &
        OLLAMA_PID=$!
        
        echo "Waiting for Ollama to respond..."
        for i in {1..30}; do
            if curl -s http://127.0.0.1:11434 > /dev/null; then
                echo "Ollama is up!"
                break
            fi
            sleep 2
        done
        
        echo ">>> [3/5] Pulling Model Weights..."
        ./ollama pull qwen2.5:8b
        
        echo ">>> [4/5] Running Dataset Generation..."
        if [ -d ".venv" ]; then
            source .venv/bin/activate
            pip install pandas
            python_exec="python"
        else
            pip install --user pandas
            python_exec="python3"
        fi

        bash ./scripts/run_full_agentdojo.sh
        
        echo ">>> [5/5] Extracting CSV Results..."
        $python_exec scripts/extract_agentdojo.py \
            --logdir data/agentdojo_runs_full \
            --out-dir dataset \
            --prefix agentdojo_full

        echo "Shutting down Ollama cleanly..."
        kill $OLLAMA_PID
     '

echo "===================================="
echo "End Time      : $(date '+%Y-%m-%d %H:%M:%S')"
echo "===================================="