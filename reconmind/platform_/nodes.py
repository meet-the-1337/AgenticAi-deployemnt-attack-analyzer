"""
reconmind.platform_.nodes
=========================
The agent node functions for the reconmind pipeline (Milestone 3).

Real LLM calls are made via the ``reconmind.llm`` client wrapper.
"""

from __future__ import annotations

import logging

from reconmind.llm import get_llm_client
from reconmind.platform_.logging_decorator import logged_node
from reconmind.platform_.prompts import (
    ACTION_SYSTEM_PROMPT,
    INTAKE_SYSTEM_PROMPT,
    RETRIEVAL_SYSTEM_PROMPT,
)
from reconmind.platform_.state import GraphState

logger = logging.getLogger(__name__)

INTAKE_AGENT_ID: str = "intake_agent"
RETRIEVAL_AGENT_ID: str = "retrieval_agent"
ACTION_AGENT_ID: str = "action_agent"
MEMORY_MANAGER_ID: str = "memory_manager"


def memory_manager_node(
    state: GraphState,
    operation: str = "read",
) -> str | None:
    """Stub memory manager."""
    run_id = state.get("run_id", "unknown")
    logger.debug(
        "[STUB] memory_manager called: op=%s run_id=%s",
        operation, run_id,
    )
    return None


@logged_node(agent_id=INTAKE_AGENT_ID, agent_role="intake")
def intake_node(state: GraphState) -> GraphState:
    raw_input: str = state.get("current_input", "")
    _ = memory_manager_node(state, operation="read")

    client = get_llm_client(role="target_agent")
    response = client.generate(
        system_prompt=INTAKE_SYSTEM_PROMPT,
        user_prompt=raw_input,
    )
    
    logger.info("[%s] generated output for: %r", INTAKE_AGENT_ID, raw_input[:40])

    agent_outputs: dict[str, str] = dict(state.get("agent_outputs") or {})
    agent_outputs[INTAKE_AGENT_ID] = response.text

    # Return updated state with new optional fields for logging
    return {
        **state,
        "current_input": response.text,
        "agent_outputs": agent_outputs,
        "model_name": response.model_name,
        "temperature": response.temperature,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
    }


@logged_node(agent_id=RETRIEVAL_AGENT_ID, agent_role="retrieval")
def retrieval_node(state: GraphState) -> GraphState:
    current_input: str = state.get("current_input", "")
    _ = memory_manager_node(state, operation="read")

    client = get_llm_client(role="target_agent")
    response = client.generate(
        system_prompt=RETRIEVAL_SYSTEM_PROMPT,
        user_prompt=current_input,
    )

    logger.info("[%s] generated output for: %r", RETRIEVAL_AGENT_ID, current_input[:40])

    agent_outputs: dict[str, str] = dict(state.get("agent_outputs") or {})
    agent_outputs[RETRIEVAL_AGENT_ID] = response.text

    return {
        **state,
        "current_input": response.text,
        "agent_outputs": agent_outputs,
        "model_name": response.model_name,
        "temperature": response.temperature,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
    }


@logged_node(agent_id=ACTION_AGENT_ID, agent_role="action")
def action_node(state: GraphState) -> GraphState:
    current_input: str = state.get("current_input", "")

    client = get_llm_client(role="target_agent")
    response = client.generate(
        system_prompt=ACTION_SYSTEM_PROMPT,
        user_prompt=current_input,
    )

    logger.info("[%s] generated output for: %r", ACTION_AGENT_ID, current_input[:40])

    _ = memory_manager_node(state, operation="write")

    agent_outputs: dict[str, str] = dict(state.get("agent_outputs") or {})
    agent_outputs[ACTION_AGENT_ID] = response.text

    return {
        **state,
        "current_input": response.text,
        "agent_outputs": agent_outputs,
        "model_name": response.model_name,
        "temperature": response.temperature,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
    }
