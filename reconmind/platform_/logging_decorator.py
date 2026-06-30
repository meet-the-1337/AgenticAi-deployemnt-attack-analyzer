"""
reconmind.platform_.logging_decorator
======================================
``@logged_node`` — the decorator that makes automatic event logging happen.

Contract
--------
Every node function wrapped with ``@logged_node(agent_id=..., agent_role=...)``
will, without any extra code in the node body:

1. Capture ``start_time`` (monotonic clock for latency + UTC wall-clock for
   timestamp).
2. Capture the pre-call ``hop_index`` from the input state (this is the
   authoritative hop value for this event — nodes must NOT mutate hop_index).
3. Call the wrapped node function.
4. Capture ``end_time``, compute ``latency_ms``.
5. Read optional fields from the result state: ``temperature``,
   ``model_name``.
6. Extract ``output_text`` from ``result["agent_outputs"][agent_id]`` —
   no ambiguous fallback (Issue 7 fix: if the node forgets to write its
   output, a WARNING is logged and an empty string is stored).
7. Increment ``hop_index`` in the result state by 1 (Issue 5 fix: nodes
   no longer manage this counter).
8. Persist a complete ``events`` row to SQLite.
9. Return the updated state to LangGraph.

The wrapped function's **signature is unchanged** — it still takes and
returns ``GraphState``.  The decorator is purely additive.

DB connection strategy
-----------------------
A new connection is opened and closed for every event write (sequential
pipeline, no concurrency in M1-M3). Milestone 7 may introduce a pool if
profiling shows this is a bottleneck; that change is isolated to this file.

Error handling
--------------
A DB write failure is logged as ERROR and re-raised — the pipeline halts
visibly rather than silently losing events.
"""

from __future__ import annotations

import functools
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from time import monotonic
from typing import Callable, Optional

from reconmind.config import cfg
from reconmind.platform_.state import GraphState

logger = logging.getLogger(__name__)

NodeFn = Callable[[GraphState], GraphState]


# ---------------------------------------------------------------------------
# Internal: write one event row
# ---------------------------------------------------------------------------

def _write_event(
    *,
    run_id: str,
    hop_index: int,
    agent_id: str,
    agent_role: str,
    input_prompt_text: str,
    output_text: str,
    model_name: str,
    latency_ms: float,
    timestamp: str,
    defense_active: int = 0,
    defense_triggered: int = 0,
    defense_confidence_score: Optional[float] = None,
    tool_called: Optional[str] = None,
    tool_result_status: Optional[str] = None,
    memory_ops_summary: Optional[str] = None,
    temperature: Optional[float] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
) -> None:
    """
    Insert a single row into the ``events`` table.

    Nullable fields (tool_called, tool_result_status, memory_ops_summary,
    defense_*, injection_*, temperature, input_tokens, output_tokens) default
    to NULL / schema defaults.  Attack/defense layers in later milestones
    populate the defense/injection fields.

    Args:
        run_id:             UUID of the parent run.
        hop_index:          0-based position of this event in the run.
        agent_id:           Agent identifier (e.g. ``"intake_agent"``).
        agent_role:         Role label (e.g. ``"intake"``).
        input_prompt_text:  The prompt / input the node received.
        output_text:        The text the node produced.
        model_name:         LLM model name (``"stub"`` or real model).
        latency_ms:         Wall-clock latency of the node call in ms.
        timestamp:          ISO-8601 UTC string when the event completed.
        temperature:        LLM sampling temperature (None for stubs).
        input_tokens:       Prompt token count (None for stubs).
        output_tokens:      Completion token count (None for stubs).

    Raises:
        sqlite3.Error: propagated on any DB failure.
    """
    event_id = str(uuid.uuid4())
    db_path = cfg.database.resolved_path

    sql = """
        INSERT INTO events (
            event_id, run_id, hop_index, agent_id, agent_role,
            input_prompt_text, output_text,
            tool_called, tool_result_status, memory_ops_summary,
            model_name, latency_ms,
            defense_active, defense_triggered, defense_confidence_score,
            injection_present_this_event, injection_outcome,
            timestamp, temperature, input_tokens, output_tokens
        ) VALUES (
            :event_id, :run_id, :hop_index, :agent_id, :agent_role,
            :input_prompt_text, :output_text,
            :tool_called, :tool_result_status, :memory_ops_summary,
            :model_name, :latency_ms,
            :defense_active, :defense_triggered, :defense_confidence_score,
            0, NULL,
            :timestamp, :temperature, :input_tokens, :output_tokens
        )
    """

    params = {
        "event_id": event_id,
        "run_id": run_id,
        "hop_index": hop_index,
        "agent_id": agent_id,
        "agent_role": agent_role,
        "input_prompt_text": input_prompt_text,
        "output_text": output_text,
        "tool_called": tool_called,
        "tool_result_status": tool_result_status,
        "memory_ops_summary": memory_ops_summary,
        "model_name": model_name,
        "latency_ms": latency_ms,
        "defense_active": defense_active,
        "defense_triggered": defense_triggered,
        "defense_confidence_score": defense_confidence_score,
        "temperature": temperature,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "timestamp": timestamp,
    }

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(sql, params)
        conn.commit()
        logger.debug(
            "Event logged: event_id=%s run=%s hop=%d agent=%s latency=%.1fms "
            "tokens=%s/%s temp=%s",
            event_id, run_id, hop_index, agent_id, latency_ms,
            input_tokens, output_tokens, temperature,
        )
    except sqlite3.Error as exc:
        logger.error(
            "Failed to log event for agent '%s' run '%s': %s",
            agent_id, run_id, exc,
        )
        raise
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# Public decorator
# ---------------------------------------------------------------------------

def logged_node(
    *,
    agent_id: str,
    agent_role: str,
) -> Callable[[NodeFn], NodeFn]:
    """
    Decorator factory for LangGraph node functions.

    Wraps a node function so that every invocation is automatically timed,
    its I/O captured, and the event persisted to the ``events`` table.
    The wrapped function's signature is unchanged.

    Responsibilities of this decorator (not the node body):
      - Time the call (latency_ms).
      - Read the pre-call hop_index for the event row.
      - Increment hop_index in the result state (nodes do NOT do this).
      - Extract output_text from result["agent_outputs"][agent_id].
      - Read temperature / token counts from the result state.
      - Write the complete event row.

    Args:
        agent_id:   Stable identifier for this agent (``"intake_agent"``).
        agent_role: Role label (``"intake"``).

    Returns:
        A decorator that accepts a ``NodeFn`` and returns a ``NodeFn``.

    Example::

        @logged_node(agent_id="intake_agent", agent_role="intake")
        def intake_node(state: GraphState) -> GraphState:
            ...

    Raises:
        sqlite3.Error: if the event write fails (pipeline halts).
    """

    def decorator(fn: NodeFn) -> NodeFn:

        @functools.wraps(fn)
        def wrapper(state: GraphState) -> GraphState:
            # Snapshot values from INPUT state before the node can mutate them.
            input_text: str = state.get("current_input", "")
            run_id: str = state.get("run_id", "unknown")
            hop_index: int = state.get("hop_index", 0)   # authoritative pre-call value
            model_name: str = state.get("model_name", "stub")

            t0 = monotonic()
            result: GraphState = fn(state)
            t1 = monotonic()

            latency_ms: float = (t1 - t0) * 1000.0
            timestamp: str = datetime.now(tz=timezone.utc).isoformat()

            # Extract output — strict: only from agent_outputs[agent_id].
            # If missing, warn and store empty string so the bug surfaces
            # in the events table rather than being silently hidden.
            output_text: str = result.get("agent_outputs", {}).get(agent_id, "")
            if not output_text:
                logger.warning(
                    "Node '%s' did not write to agent_outputs['%s']. "
                    "output_text will be empty in events table.",
                    fn.__name__, agent_id,
                )

            # Optional per-event LLM metadata (None for stub nodes).
            temperature: Optional[float] = result.get("temperature")
            input_tokens: Optional[int] = result.get("input_tokens")
            output_tokens: Optional[int] = result.get("output_tokens")
            tool_called: Optional[str] = result.get("tool_called")
            tool_result_status: Optional[str] = result.get("tool_result_status")
            memory_ops_summary: Optional[str] = result.get("memory_ops_summary")

            _write_event(
                run_id=run_id,
                hop_index=hop_index,
                agent_id=agent_id,
                agent_role=agent_role,
                input_prompt_text=input_text,
                output_text=output_text,
                tool_called=tool_called,
                tool_result_status=tool_result_status,
                memory_ops_summary=memory_ops_summary,
                model_name=model_name,
                latency_ms=latency_ms,
                timestamp=timestamp,
                defense_active=1 if getattr(result, "get", lambda k: False)("defense_active") else 0,
                defense_triggered=1 if getattr(result, "get", lambda k: False)("defense_triggered") else 0,
                defense_confidence_score=getattr(result, "get", lambda k: None)("defense_confidence_score"),
                temperature=temperature,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            # Increment hop_index here, not in node bodies (Issue 5 fix).
            # This guarantees correct ordering even with conditional edges.
            return {**result, "hop_index": hop_index + 1}

        return wrapper

    return decorator
