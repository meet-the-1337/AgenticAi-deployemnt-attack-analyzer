# ReconMind - Agentic AI Security Pipeline

Welcome to the ReconMind project! This repository contains the code and data for the Multi-Agent System security anomaly detection pipeline.

## Getting Started

To ensure a smooth setup without version conflicts or messing up your global Python packages, we use a virtual environment (`.venv`). This contains all the necessary dependencies in an isolated space. 

### 1. Setting up the Virtual Environment
First, create your own virtual environment in the project root:
```bash
python3 -m venv .venv
```

Next, activate the virtual environment:
- On **Linux/macOS**:
  ```bash
  source .venv/bin/activate
  ```
- On **Windows**:
  ```bash
  .venv\Scripts\activate
  ```

### 2. Installing Requirements
Once your virtual environment is active (you'll usually see `(.venv)` in your terminal prompt), install all the project dependencies from `requirements.txt`:
```bash
pip install -r requirements.txt
```
*(This includes all the required deep learning models like torch, xgboost, pandas, scikit-learn, and FastAPI).*

### Note on Temporary Files
You might notice some directories and files like `.venv/`, `__pycache__/`, or `.~lock.*` files in your local copy. 
- **`.venv/`**: This is your local virtual environment folder. It is ignored by Git because dependencies can be quite large and are OS-specific. You should always recreate it on your machine.
- **`__pycache__/` & `.pytest_cache/`**: These are temporary python bytecode/cache files generated automatically when you run scripts. They speed up execution and are also ignored by Git. 
- **`.db` and lock files**: These are local database or temporary lock files created by tools and shouldn't be committed. 

This keeps our Git repository clean and focused only on the source code!
