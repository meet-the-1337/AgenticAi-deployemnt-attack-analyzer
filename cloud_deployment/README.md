# ReconMind Cloud GPU Dataset Generator

This package contains everything you need to generate the full AgentDojo dataset on a remote, cloud-based GPU.

## Prerequisites
Before you begin, ensure your cloud GPU instance has the following:
1. **Python 3.10+** installed.
2. **Ollama** installed (or vLLM).
3. **tmux** or **screen** installed (to keep the session alive if SSH disconnects).

## Procedure

### 1. Upload and Unzip
Upload this `reconmind_dataset_gen.zip` to your cloud GPU instance and unzip it.
```bash
unzip reconmind_dataset_gen.zip
cd cloud_deployment
```

### 2. Set Up the Environment
Run the setup script. This will create a Python virtual environment, install the required packages, and apply the ReconMind specific patches to AgentDojo (which fixes the `max_tokens` hang issue).
```bash
chmod +x setup_env.sh
./setup_env.sh
```

### 3. Start the LLM Backend
Make sure your LLM server is running in the background. If you are using Ollama:
```bash
ollama serve &
# Replace qwen2.5:8b with the model you specified in run_full_agentdojo.sh
ollama pull qwen2.5:8b
```

### 4. Start the Full Benchmark Generation
Because this process can take hours and SSH connections can drop, you **MUST** run this inside `tmux`.

```bash
# Open a tmux session
tmux new -s dataset_gen

# Activate the virtual environment
source .venv/bin/activate

# Run the generation script
./scripts/run_full_agentdojo.sh
```
*(You can safely detach from the tmux session by pressing `Ctrl+B` and then `D`. You can log off and check back later by reconnecting and typing `tmux attach -t dataset_gen`).*

### 5. Extract the Results to CSV
Once the generation finishes, it will print a completion message. You must then run the extractor script to convert the AgentDojo JSON logs into our custom `runs.csv` and `events.csv` format:

```bash
# Ensure your virtual environment is still active
source .venv/bin/activate

# Run the extractor
.venv/bin/python scripts/extract_agentdojo.py \
    --logdir data/agentdojo_runs_full \
    --out-dir dataset \
    --prefix agentdojo_full
```

This will produce `dataset/agentdojo_full_runs.csv` and `dataset/agentdojo_full_events.csv`. You can then securely download this `dataset/` directory back to your local machine!
