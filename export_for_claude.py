import os
from pathlib import Path

REPO_ROOT = Path("/home/ms/all projects/AGENTIC-AI + ML/reconmind")

FILES_TO_EXPORT = [
    "config.yaml",
    "reconmind/config.py",
    "reconmind/platform_/state.py",
    "reconmind/platform_/prompts.py",
    "reconmind/platform_/memory.py",
    "reconmind/platform_/tools.py",
    "reconmind/platform_/logging_decorator.py",
    "reconmind/platform_/nodes.py",
    "reconmind/platform_/graph.py",
    "reconmind/db/schema.sql",
    "reconmind/db/init_db.py",
    "reconmind/attacks/base.py",
    "reconmind/attacks/direct_injection.py",
    "reconmind/verify/oracle.py",
    "reconmind/verify/tool_check.py",
    "reconmind/verify/judge_check.py",
    "reconmind/defenses/base.py",
    "reconmind/defenses/heuristic.py",
    "reconmind/api/server.py",
    "reconmind/api/routes.py",
    "frontend/src/App.jsx",
    "frontend/src/components/PromptConsole.jsx",
    "frontend/src/components/FlowChart.jsx",
    "frontend/src/api/client.js"
]

OUTPUT_FILE = REPO_ROOT / "claude_codebase_export.md"

def get_ext(path: str) -> str:
    ext = path.split('.')[-1]
    if ext == 'py': return 'python'
    if ext == 'js' or ext == 'jsx': return 'javascript'
    if ext == 'yaml': return 'yaml'
    if ext == 'sql': return 'sql'
    return 'text'

with OUTPUT_FILE.open("w", encoding="utf-8") as out:
    out.write("# ReconMind Codebase Export (Up to M8.5)\n\n")
    out.write("This document contains the core implementation of the ReconMind Agentic Security Pipeline for architectural review.\n\n")
    
    for rel_path in FILES_TO_EXPORT:
        full_path = REPO_ROOT / rel_path
        if full_path.exists():
            out.write(f"## File: `{rel_path}`\n\n")
            lang = get_ext(rel_path)
            out.write(f"```{lang}\n")
            with full_path.open("r", encoding="utf-8") as f:
                out.write(f.read())
            out.write("\n```\n\n")
        else:
            out.write(f"## File: `{rel_path}` (NOT FOUND)\n\n")

print(f"Export created at {OUTPUT_FILE}")
