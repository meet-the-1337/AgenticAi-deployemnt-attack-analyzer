"""
reconmind.platform_.state
=========================
Shared graph state schema that flows through every LangGraph node.

This TypedDict is the **single contract** between all nodes.  Every node
receives a ``GraphState`` dict and must return a ``GraphState``-compatible
dict with the keys it mutated.  LangGraph merges the returned dict into the
running state automatically.

Design notes
------------
- ``_GraphStateRequired`` (total=True) declares fields every caller **must**
  supply.  A missing required field causes a ``KeyError`` at the call site,
  not a silent ``None`` deep inside a node.  Fixes the ``total=False``
  anti-pattern from M2 (architectural review Issue 4).
- ``GraphState`` inherits from ``_GraphStateRequired`` with ``total=False``
  for the genuinely optional fields (``memory_ref``, ``temperature``).
- Using ``TypedDict`` (not Pydantic) keeps state natively serialisable by
  LangGraph's built-in checkpointer without extra configuration.
- ``hop_index`` is managed exclusively by the ``@logged_node`` decorator.
  Node bodies must NOT increment it — doing so would break any graph that
  has conditional edges (Issue 5 fix).
"""

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict


class _GraphStateRequired(TypedDict):
    """Fields every pipeline caller must supply before invoking the graph."""

    session_id: str
    """Human-readable identifier for this session (e.g. a scenario slug).
    Set once by the caller; nodes treat it as read-only."""

    run_id: str
    """UUID for the current simulation run. Matches ``runs.run_id`` in the DB.
    Set once by the caller; nodes treat it as read-only."""

    hop_index: int
    """0-based counter managed by ``@logged_node``. Nodes must NOT modify this.
    Used as the primary ordering key in the ``events`` table."""

    current_input: str
    """The payload arriving at this node — either the original prompt or the
    output of the previous node. Each node reads this and writes its response
    to ``agent_outputs``."""

    agent_outputs: dict[str, str]
    """Accumulator keyed by agent_id → output_text. Populated by every node
    so downstream nodes and scripts can inspect the full chain."""

    model_name: str
    """Name of the LLM model in use for this run (e.g. ``"qwen3:8b"``,
    ``"stub"``). Written once by the pipeline entry-point; echoed into every
    event row."""


class GraphState(_GraphStateRequired, total=False):
    """
    Full graph state dict passed between every node in the LangGraph pipeline.

    Required fields are inherited from ``_GraphStateRequired`` (total=True).
    Optional fields declared here (total=False).
    """

    memory_ref: Optional[str]
    """Placeholder for a memory-store reference (populated in Milestone 6).
    Nodes may read it but must not depend on it being non-None yet."""

    temperature: Optional[float]
    """LLM sampling temperature used by the most recent node call.
    Set by node bodies after each LLM call so the decorator can log it
    to the events table. NULL for stub/non-LLM events."""
