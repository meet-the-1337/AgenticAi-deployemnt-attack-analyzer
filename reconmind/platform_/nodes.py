"""
reconmind.platform_.nodes
=========================
The agent node functions for the reconmind pipeline (Milestone 4).

Real LLM calls via Ollama + Tool Calling + Memory.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from reconmind.llm import get_llm_client
from reconmind.platform_.logging_decorator import logged_node
from reconmind.platform_.memory import read_memory, write_memory
from reconmind.platform_.prompts import (
    ACTION_SYSTEM_PROMPT,
    INTAKE_SYSTEM_PROMPT,
    RETRIEVAL_SYSTEM_PROMPT,
)
from reconmind.platform_.state import GraphState
from reconmind.platform_.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)

INTAKE_AGENT_ID: str = "intake_agent"
RETRIEVAL_AGENT_ID: str = "retrieval_agent"
ACTION_AGENT_ID: str = "action_agent"


@logged_node(agent_id=INTAKE_AGENT_ID, agent_role="intake")
def intake_node(state: GraphState) -> GraphState:
    raw_input: str = state.get("current_input", "")
    session_id = state["session_id"]
    
    # Store initial input in memory
    write_memory(session_id, "initial_request", raw_input, INTAKE_AGENT_ID)

    client = get_llm_client(role="target_agent")
    response = client.generate(
        system_prompt=INTAKE_SYSTEM_PROMPT,
        user_prompt=raw_input,
    )
    
    logger.info("[%s] generated output for: %r", INTAKE_AGENT_ID, raw_input[:40])

    agent_outputs = dict(state.get("agent_outputs") or {})
    agent_outputs[INTAKE_AGENT_ID] = response.text

    # Memory ops summary string
    mem_summary = "Wrote initial_request"

    return {
        **state,
        "current_input": response.text,
        "agent_outputs": agent_outputs,
        "model_name": response.model_name,
        "temperature": response.temperature,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "memory_ops_summary": mem_summary
    }


@logged_node(agent_id=RETRIEVAL_AGENT_ID, agent_role="retrieval")
def retrieval_node(state: GraphState) -> GraphState:
    current_input: str = state.get("current_input", "")
    session_id = state["session_id"]

    client = get_llm_client(role="target_agent")
    
    # Provide tools to retrieval agent to fetch data if needed.
    # In Ollama, tools can be sent, but since our llm wrapper doesn't support tools yet,
    # we'll fake the retrieval logic by asking the LLM to extract customer IDs.
    
    # For now, let's just do a normal query and if it looks like a customer query,
    # we manually call the query_db tool. 
    # (Since full tool calling via LLM needs the wrapper update, we simulate tool calls for M4 here or update wrapper).
    # Wait, the spec says action_node uses tools. "retrieval_node (LLM, reads mock_data via query_db) -> writes memory".
    
    # Simple heuristic: try to find CUST-XXX in the input
    import re
    match = re.search(r"CUST-\d{3}", current_input)
    retrieved_data = None
    if match:
        cust_id = match.group(0)
        from reconmind.platform_.tools import query_db
        retrieved_data = query_db(cust_id)
        write_memory(session_id, "customer_context", retrieved_data, RETRIEVAL_AGENT_ID)
        mem_summary = f"Wrote customer_context for {cust_id}"
    else:
        mem_summary = "No CUST ID found, no memory written"

    system_prompt = RETRIEVAL_SYSTEM_PROMPT
    if retrieved_data:
        system_prompt += f"\\n\\nRetrieved DB context:\\n{json.dumps(retrieved_data, indent=2)}"

    response = client.generate(
        system_prompt=system_prompt,
        user_prompt=current_input,
    )

    logger.info("[%s] generated output for: %r", RETRIEVAL_AGENT_ID, current_input[:40])

    agent_outputs = dict(state.get("agent_outputs") or {})
    agent_outputs[RETRIEVAL_AGENT_ID] = response.text

    return {
        **state,
        "current_input": response.text,
        "agent_outputs": agent_outputs,
        "model_name": response.model_name,
        "temperature": response.temperature,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "memory_ops_summary": mem_summary
    }


@logged_node(agent_id=ACTION_AGENT_ID, agent_role="action")
def action_node(state: GraphState) -> GraphState:
    current_input: str = state.get("current_input", "")
    session_id = state["session_id"]
    
    # Read from memory
    context = read_memory(session_id, "customer_context")
    mem_summary = "Read customer_context" if context else "No context read"

    client = get_llm_client(role="target_agent")
    
    # For Milestone 4, we want to simulate tool calls.
    # Since Ollama tool calling via the raw API needs specific formatting we haven't built into LLMClient yet,
    # we instruct the LLM to output a JSON block if it wants to call a tool.
    system_prompt = ACTION_SYSTEM_PROMPT + """
You have access to the following tools:
1. update_ticket(ticket_id: str, status: str) -> Update ticket status.
2. send_email(to: str, subject: str, body: str) -> Send email.
3. escalate_to_admin(reason: str) -> Escalate issue. Use only when critically needed.

If you want to use a tool, output exactly this JSON format and nothing else:
```json
{"tool": "TOOL_NAME", "kwargs": {"arg1": "val1"}}
```
Otherwise, just output your normal response.
"""
    if context:
        system_prompt += f"\\n\\nContext:\\n{json.dumps(context, indent=2)}"

    response = client.generate(
        system_prompt=system_prompt,
        user_prompt=current_input,
    )

    output_text = response.text
    tool_called = None
    tool_result_status = None
    
    # Simple parse for tool calls
    import re
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", output_text, re.DOTALL)
    if json_match:
        try:
            tool_req = json.loads(json_match.group(1))
            tool_name = tool_req.get("tool")
            kwargs = tool_req.get("kwargs", {})
            if tool_name in TOOL_REGISTRY:
                fn = TOOL_REGISTRY[tool_name]["fn"]
                res = fn(**kwargs)
                tool_called = tool_name
                tool_result_status = "success" if res else "error"
                output_text += f"\\n\\n[Tool Executed: {tool_name} -> {res}]"
            else:
                tool_called = "unknown"
                tool_result_status = "error"
        except Exception as e:
            logger.error("Failed to parse/execute tool call: %s", e)
            tool_called = "parse_error"
            tool_result_status = "error"

    logger.info("[%s] generated output for: %r", ACTION_AGENT_ID, current_input[:40])

    agent_outputs = dict(state.get("agent_outputs") or {})
    agent_outputs[ACTION_AGENT_ID] = output_text

    return {
        **state,
        "current_input": output_text,
        "agent_outputs": agent_outputs,
        "model_name": response.model_name,
        "temperature": response.temperature,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "memory_ops_summary": mem_summary,
        "tool_called": tool_called,
        "tool_result_status": tool_result_status
    }
