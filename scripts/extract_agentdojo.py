"""
scripts/extract_agentdojo.py
============================
Converts AgentDojo benchmark JSON log files → ReconMind CSV schema.

AgentDojo TaskResults structure (verified against v0.1.35):
  suite_name         : str
  pipeline_name      : str
  user_task_id       : str
  injection_task_id  : str | None
  attack_type        : str | None     ← attack key name e.g. "direct", "ignore_previous"
  injections         : dict[str, str] ← placeholder → injection payload
  messages           : list[ChatMessage]  ← full conversation
  error              : str | None
  utility            : bool           ← did agent complete the user task?
  security           : bool           ← did the injection FAIL to succeed? (True = SECURE)
  duration           : float          ← total run duration in seconds

NOTE on 'security' semantics in AgentDojo:
  security = True  → agent resisted injection (attack FAILED)
  security = False → agent was hijacked (attack SUCCEEDED)
  So: attack_success_binary = 1 if security == False else 0

Usage (from repo root with .venv active):
  .venv/bin/python scripts/extract_agentdojo.py \\
      --logdir data/agentdojo_runs \\
      --out-dir dataset \\
      --prefix agentdojo

Output files:
  dataset/agentdojo_runs.csv
  dataset/agentdojo_events.csv
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# LABEL MAPPINGS  (must match deep_model.py exactly)
# ─────────────────────────────────────────────────────────────────────

# AgentDojo attack_type string → your injection_type
# AgentDojo attacks that inject into tool returns = indirect
# Attacks that modify the user message directly = direct
# DoS attacks = tool_misuse (they abuse tool calling loop)
ATTACK_TYPE_MAP: dict[str | None, str] = {
    None:                                   "",                  # clean run
    "direct":                               "direct_injection",
    "ignore_previous":                      "direct_injection",
    "system_message":                       "direct_injection",
    "manual":                               "direct_injection",
    "injecagent":                           "indirect_injection",
    "important_instructions":              "indirect_injection",
    "important_instructions_no_user_name": "indirect_injection",
    "important_instructions_no_model_name":"indirect_injection",
    "important_instructions_no_names":     "indirect_injection",
    "important_instructions_wrong_model_name": "indirect_injection",
    "important_instructions_wrong_user_name":  "indirect_injection",
    "tool_knowledge":                       "tool_misuse",
    "dos":                                  "dos",
    "swearwords_dos":                       "dos",
    "captcha_dos":                          "dos",
    "offensive_email_dos":                  "dos",
    "felony_dos":                           "dos",
}

# (utility, injection_succeeded) → injection_outcome
# security=True means attack FAILED, so injection_succeeded = not security
OUTCOME_MAP: dict[tuple[bool, bool], str] = {
    (True,  False): "ignored",       # user task succeeded, attack failed
    (True,  True):  "full_success",  # user task succeeded, attack also succeeded
    (False, True):  "partial",       # user task failed, attack succeeded
    (False, False): "clean",         # both failed / no attack
}

# AgentDojo suite → attack_objective heuristic
SUITE_OBJECTIVE_MAP: dict[str, str] = {
    "workspace": "data_exfiltration",     # emails, files — attacker wants data
    "banking":   "unauthorized_action",   # money transfers — attacker wants transactions
    "travel":    "unauthorized_action",   # bookings — attacker wants reservations
    "slack":     "data_exfiltration",     # messages — attacker wants message content
}

# Attack strength — AgentDojo doesn't expose this natively;
# we derive from attack payload complexity (length proxy)
def _estimate_strength(injections: dict[str, str]) -> str:
    if not injections:
        return ""
    total_len = sum(len(v) for v in injections.values())
    if total_len < 80:
        return "subtle"
    elif total_len < 300:
        return "moderate"
    else:
        return "blatant"


# ─────────────────────────────────────────────────────────────────────
# MESSAGE PARSING HELPERS
# ─────────────────────────────────────────────────────────────────────

def _extract_text(content: list[dict] | str | None) -> str:
    """Extract plain text from a list of content blocks."""
    if not content:
        return ""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("content", block.get("text", ""))))
        elif isinstance(block, str):
            parts.append(block)
    return " ".join(parts).strip()


def _parse_messages_to_3_hops(
    messages: list[dict],
    duration_s: float,
) -> list[dict]:
    """
    Parse AgentDojo message list into exactly 3 hops for ReconMind.

    AgentDojo conversation structure:
      system   → system prompt
      user     → user task
      assistant → LLM response (may contain tool_calls)
      tool     → tool result (may contain injected content at hop 1)
      assistant → next LLM response
      tool     → next tool result
      ...

    We map:
      hop 0 (intake)    = first user+assistant pair
      hop 1 (retrieval) = first tool call + tool result pair
      hop 2 (action)    = last assistant message + final tool call (if any)
    """
    hops: list[dict] = []

    # Collect messages by role
    system_msgs  = [m for m in messages if m.get("role") == "system"]
    user_msgs    = [m for m in messages if m.get("role") == "user"]
    asst_msgs    = [m for m in messages if m.get("role") == "assistant"]
    tool_msgs    = [m for m in messages if m.get("role") == "tool"]

    system_text = _extract_text(system_msgs[0].get("content")) if system_msgs else ""
    user_text   = _extract_text(user_msgs[0].get("content"))   if user_msgs   else ""

    # Hop 0 — intake agent
    # Input: system + user task
    # Output: first assistant message
    hop0_in  = f"[SYSTEM] {system_text[:256]} [USER] {user_text[:512]}"
    hop0_out = ""
    hop0_tool = ""
    hop0_args = ""
    if asst_msgs:
        hop0_out = _extract_text(asst_msgs[0].get("content")) or ""
        tc = asst_msgs[0].get("tool_calls")
        if tc:
            hop0_tool = tc[0].get("function", tc[0].get("name", "")) if isinstance(tc[0], dict) else str(tc[0])
            hop0_args = tc[0].get("arguments", tc[0].get("args", "")) if isinstance(tc[0], dict) else ""

    # Hop 1 — retrieval agent
    hop1_in  = ""
    hop1_out = ""
    hop1_tool = ""
    hop1_args = ""
    if tool_msgs:
        hop1_in = _extract_text(tool_msgs[0].get("content")) or ""
    if len(asst_msgs) >= 2:
        hop1_out = _extract_text(asst_msgs[1].get("content")) or ""
        tc = asst_msgs[1].get("tool_calls")
        if tc:
            hop1_tool = tc[0].get("function", tc[0].get("name", "")) if isinstance(tc[0], dict) else str(tc[0])
            hop1_args = tc[0].get("arguments", tc[0].get("args", "")) if isinstance(tc[0], dict) else ""
    elif len(asst_msgs) == 1 and not hop1_out:
        hop1_out = hop0_out

    # Hop 2 — action agent
    hop2_in  = ""
    hop2_out = ""
    hop2_tool = ""
    hop2_args = ""
    if len(tool_msgs) >= 2:
        hop2_in = _extract_text(tool_msgs[-1].get("content")) or hop1_in
    elif tool_msgs:
        hop2_in = _extract_text(tool_msgs[-1].get("content")) or ""
    if asst_msgs:
        last_asst = asst_msgs[-1]
        hop2_out  = _extract_text(last_asst.get("content")) or ""
        tc = last_asst.get("tool_calls")
        if tc:
            hop2_tool = tc[0].get("function", tc[0].get("name", "")) if isinstance(tc[0], dict) else str(tc[0])
            hop2_args = tc[0].get("arguments", tc[0].get("args", "")) if isinstance(tc[0], dict) else ""

    per_hop_latency = (duration_s * 1000.0) / 3.0

    roles = ["intake", "retrieval", "action"]
    agent_ids = ["intake_agent", "retrieval_agent", "action_agent"]
    inputs  = [hop0_in,  hop1_in,  hop2_in]
    outputs = [hop0_out, hop1_out, hop2_out]
    tools   = [hop0_tool, hop1_tool, hop2_tool]
    args    = [hop0_args, hop1_args, hop2_args]

    for i in range(3):
        inp = inputs[i] or f"[{roles[i].upper()} hop {i} — no content]"
        out = outputs[i] or f"[{roles[i].upper()} hop {i} — no output]"
        inp_tok = len(inp.split())
        out_tok = len(out.split())
        hops.append({
            "hop_index":         i,
            "agent_role":        roles[i],
            "agent_id":          agent_ids[i],
            "input_prompt_text": inp[:1024],
            "output_text":       out[:1024],
            "tool_called":       tools[i],
            "tool_args":         str(args[i])[:512],
            "input_tokens":      inp_tok,
            "output_tokens":     out_tok,
            "latency_ms":        round(per_hop_latency, 3),
        })
    return hops


# ─────────────────────────────────────────────────────────────────────
# TASK RESULT → ROW BUILDER
# ─────────────────────────────────────────────────────────────────────

def result_to_rows(
    result: dict,
    defense_name: str = "none",
) -> tuple[dict, list[dict]]:
    """
    Convert one AgentDojo TaskResults dict into:
      - one runs row
      - three events rows (one per hop)
    Returns (run_row, [hop0, hop1, hop2]).
    """
    run_id = str(uuid.uuid4())

    attack_type_raw   = result.get("attack_type")        # e.g. "direct", None
    utility           = bool(result.get("utility", False))
    security_held     = bool(result.get("security", True))  # True = attack failed
    injections        = result.get("injections", {}) or {}
    duration_s        = float(result.get("duration", 0.0))
    suite_name        = result.get("suite_name", "unknown")
    messages_raw      = result.get("messages", [])

    # Derive your labels
    injection_succeeded = not security_held   # security=True means ATTACK FAILED
    injection_type      = ATTACK_TYPE_MAP.get(attack_type_raw, "indirect_injection")
    original_attack_type = attack_type_raw if attack_type_raw else "none"
    # If no attack, it's a clean run
    if attack_type_raw is None:
        injection_type = ""
        injection_succeeded = False

    outcome_key     = (utility, injection_succeeded)
    injection_outcome = OUTCOME_MAP.get(outcome_key, "clean")

    attack_success_binary = 1 if injection_succeeded else 0
    attack_strength       = _estimate_strength(injections)
    attack_objective      = SUITE_OBJECTIVE_MAP.get(suite_name, "unauthorized_action") if injection_type else ""
    is_attack             = injection_type != ""

    # Defense signals
    defense_active      = 1 if defense_name and defense_name != "none" else 0
    # We derive defense_triggered at hop level (retrieval hop = where injection hits)
    defense_triggered   = 1 if (defense_active and is_attack) else 0
    # Confidence score: estimate from outcome
    if defense_active and is_attack:
        defense_confidence = 0.85 if not injection_succeeded else 0.30
    else:
        defense_confidence = 0.0

    run_row = {
        "run_id":                run_id,
        "scenario_id":           f"{suite_name}_{result.get('user_task_id', 'unknown')}",
        "injection_type":        injection_type,
        "original_attack_type":  original_attack_type,
        "injection_outcome":     injection_outcome,
        "attack_success_binary": attack_success_binary,
        "defense_config":        defense_name,
        "attack_strength":       attack_strength,
        "attack_objective":      attack_objective,
        "source_framework":      "agentdojo",
        "environment_domain":    suite_name,
        "agent_config":          result.get("pipeline_name", ""),
        "duration_s":            round(duration_s, 4),
        "task_completed":        int(utility),
        "metadata_json":         json.dumps({"user_task_id": result.get("user_task_id", ""), "injection_task_id": result.get("injection_task_id", "")}),
    }

    # Parse messages into 3 hops
    hops = _parse_messages_to_3_hops(messages_raw, duration_s)

    events_rows = []
    for hop in hops:
        # Inject defense signals on retrieval hop (hop 1 = where injection lands)
        is_retrieval = (hop["hop_index"] == 1)
        events_rows.append({
            "run_id":                    run_id,
            "hop_index":                 hop["hop_index"],
            "agent_role":                hop["agent_role"],
            "agent_id":                  hop["agent_id"],
            "input_prompt_text":         hop["input_prompt_text"],
            "output_text":               hop["output_text"],
            "tool_called":               hop["tool_called"],
            "tool_args":                 hop.get("tool_args", ""),
            "input_tokens":              hop["input_tokens"],
            "output_tokens":             hop["output_tokens"],
            "latency_ms":                hop["latency_ms"],
            "defense_triggered":         int(defense_triggered and is_retrieval),
            "defense_active":            defense_active,
            "defense_confidence_score":  defense_confidence if (defense_active and is_retrieval) else 0.0,
        })

    return run_row, events_rows


# ─────────────────────────────────────────────────────────────────────
# LOG FILE LOADING
# ─────────────────────────────────────────────────────────────────────

def load_agentdojo_logs(logdir: Path) -> list[tuple[dict, str]]:
    """
    Walk logdir recursively, load all .json files.
    Returns list of (task_result_dict, defense_name).
    AgentDojo stores one TaskResults JSON per task run.
    """
    results = []
    json_files = list(logdir.rglob("*.json"))
    logger.info(f"Found {len(json_files)} JSON log files in {logdir}")

    for fpath in json_files:
        # Infer defense from directory structure
        # AgentDojo saves to: logdir/{pipeline_name}/{suite_name}/...
        # pipeline_name often contains defense info e.g. "gpt-4o_tool_filter"
        parts = fpath.parts
        defense_name = "none"
        for part in parts:
            if "tool_filter" in part:
                defense_name = "tool_filter"
                break
            elif "transformers_pi" in part or "pi_detector" in part:
                defense_name = "judge"
                break
            elif "spotlighting" in part or "repeat_user" in part:
                defense_name = "heuristic"
                break

        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)

            # AgentDojo saves either a single TaskResult or a list
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        results.append((item, defense_name))
            elif isinstance(data, dict):
                # Single result
                results.append((data, defense_name))

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Skipping {fpath}: {e}")

    logger.info(f"Loaded {len(results)} task results")
    return results


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract AgentDojo benchmark logs → ReconMind CSV schema"
    )
    parser.add_argument(
        "--logdir", type=Path, default=Path("data/agentdojo_runs"),
        help="Directory containing AgentDojo JSON log files (searched recursively)"
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("dataset"),
        help="Output directory for CSV files"
    )
    parser.add_argument(
        "--prefix", type=str, default="agentdojo",
        help="Filename prefix for output CSVs"
    )
    parser.add_argument(
        "--min-messages", type=int, default=2,
        help="Minimum number of messages required in a trace (skip shorter ones)"
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    if not args.logdir.exists():
        logger.error(f"logdir does not exist: {args.logdir}")
        logger.info("Run the AgentDojo benchmark first:")
        logger.info(
            "  .venv/bin/python -m agentdojo.scripts.benchmark "
            "-s workspace -s banking --attack important_instructions "
            "--logdir data/agentdojo_runs"
        )
        return

    raw_results = load_agentdojo_logs(args.logdir)
    if not raw_results:
        logger.warning("No results found. Check that --logdir contains .json files.")
        return

    runs_rows: list[dict] = []
    events_rows: list[dict] = []
    skipped = 0

    for result_dict, defense_name in raw_results:
        messages = result_dict.get("messages", [])
        if len(messages) < args.min_messages:
            skipped += 1
            continue

        run_row, hop_rows = result_to_rows(result_dict, defense_name)
        runs_rows.append(run_row)
        events_rows.extend(hop_rows)

    logger.info(f"Extracted: {len(runs_rows)} runs, {len(events_rows)} events. Skipped: {skipped}")

    # Label distribution
    if runs_rows:
        runs_df = pd.DataFrame(runs_rows)
        events_df = pd.DataFrame(events_rows)

        # Deduplicate exact traces
        import hashlib
        run_signatures = set()
        unique_run_ids = []
        runs_lookup = runs_df.set_index('run_id')
        for rid, grp in events_df.groupby('run_id'):
            sorted_grp = grp.sort_values('hop_index')
            row = runs_lookup.loc[rid]
            scenario = str(row.get('scenario_id', ''))
            inj_type = str(row.get('injection_type', ''))
            
            # Behavioral hash: scenario + injection + sequence of tools called + tool arguments + tool output length
            sig_text = scenario + "_" + inj_type + "_" + "".join(
                sorted_grp['tool_called'].astype(str) + "_" + 
                sorted_grp['tool_args'].astype(str) + "_" + 
                sorted_grp['output_tokens'].astype(str)
            )
            sig = hashlib.md5(sig_text.encode('utf-8')).hexdigest()
            if sig not in run_signatures:
                run_signatures.add(sig)
                unique_run_ids.append(rid)
                
        runs_df = runs_df[runs_df['run_id'].isin(unique_run_ids)]
        events_df = events_df[events_df['run_id'].isin(unique_run_ids)]
        logger.info(f"After deduplication: {len(runs_df)} unique runs.")

        runs_out   = args.out_dir / f"{args.prefix}_runs.csv"
        events_out = args.out_dir / f"{args.prefix}_events.csv"
        runs_df.to_csv(runs_out, index=False)
        events_df.to_csv(events_out, index=False)

        logger.info(f"Saved: {runs_out} ({len(runs_df)} rows)")
        logger.info(f"Saved: {events_out} ({len(events_df)} rows)")

        print("\n=== Label Distribution ===")
        print("injection_type:")
        print(runs_df["injection_type"].value_counts().to_string())
        print("\ninjection_outcome:")
        print(runs_df["injection_outcome"].value_counts().to_string())
        print("\nattack_success_binary:")
        print(runs_df["attack_success_binary"].value_counts().to_string())
        print("\ndefense_config:")
        print(runs_df["defense_config"].value_counts().to_string())
        print()
    else:
        logger.error("No valid runs extracted.")


if __name__ == "__main__":
    main()
