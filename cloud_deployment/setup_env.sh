#!/usr/bin/env bash
# cloud_deployment/setup_env.sh
# Sets up the AgentDojo environment and applies local LLM patches

set -e

echo "=========================================="
echo " ReconMind: Cloud GPU Environment Setup"
echo "=========================================="

echo "[1/4] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "[2/4] Upgrading pip and installing requirements..."
pip install --upgrade pip
pip install agentdojo pandas

echo "[3/4] Applying ReconMind patches to AgentDojo..."
# Find where agentdojo is installed
SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
TARGET_FILE="${SITE_PACKAGES}/agentdojo/agent_pipeline/llms/local_llm.py"

if [ -f "patches/local_llm.py" ]; then
    cp patches/local_llm.py "$TARGET_FILE"
    echo "  -> Patched local_llm.py with max_tokens and temperature fix."
else
    echo "  [!] Warning: patches/local_llm.py not found!"
fi

echo "[4/4] Making execution scripts executable..."
chmod +x scripts/run_full_agentdojo.sh

echo "=========================================="
echo " Setup Complete!"
echo " Next steps:"
echo " 1. Make sure Ollama/vLLM is running locally."
echo " 2. Run: source .venv/bin/activate"
echo " 3. Run: ./scripts/run_full_agentdojo.sh"
echo "=========================================="
