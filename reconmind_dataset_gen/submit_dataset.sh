#!/bin/bash
#SBATCH --job-name=agentdojo-gen
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --gres=gpu:2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --output=job_output_%j.txt
#SBATCH --error=job_error_%j.txt

echo "===================================="
echo "Job ID        : $SLURM_JOB_ID"
echo "Start Time    : $(date '+%Y-%m-%d %H:%M:%S')"
echo "===================================="

# Notice we added --container-workdir=/workspace so everything runs inside the mounted folder
srun --mpi=pmi2 --gres=gpu:2\
     --container-image=/home/hpc_apps/nvidia+pytorch+25.04-py3.sqsh \
     --container-mounts=$PWD:/workspace \
     --container-workdir=/workspace \
     bash -c "
        echo '>>> [1/4] Setting up Python Environment...'
        bash ./setup_env.sh

        echo '>>> [2/4] Downloading and Starting standalone Ollama (No Root)...'
        curl -L https://ollama.com/download/ollama-linux-amd64 -o ollama
        chmod +x ollama
        
        export OLLAMA_HOST='0.0.0.0:11434'
        export OLLAMA_MODELS='/workspace/ollama_models'
        
        ./ollama serve &
        sleep 10
        
        echo '>>> [3/4] Pulling Model Weights...'
        ./ollama pull qwen2.5:8b
        
        echo '>>> [4/4] Running Dataset Generation...'
        source .venv/bin/activate
        bash ./scripts/run_full_agentdojo.sh
        
        echo '>>> [5/4] Extracting CSV Results...'
        .venv/bin/python scripts/extract_agentdojo.py \
            --logdir data/agentdojo_runs_full \
            --out-dir dataset \
            --prefix agentdojo_full
     "

echo "===================================="
echo "End Time      : $(date '+%Y-%m-%d %H:%M:%S')"
echo "===================================="
