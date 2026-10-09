"""
reconmind.platform_.graph
=========================
LangGraph StateGraph wiring for the reconmind agent pipeline.

Graph topology (Milestone 2)
----------------------------

    ┌──────────────────────────────────────────────────┐
    │                  StateGraph                       │
    │                                                   │
    │   START ──► intake_node ──► retrieval_node        │
    │                                ──► action_node    │
    │                                       ──► END     │
    └──────────────────────────────────────────────────┘

``memory_manager_node`` is NOT in the graph — it is a utility called inside
individual nodes.  See ``nodes.py`` for the rationale.

Public API
----------
``build_graph() -> CompiledGraph``
    Constructs and compiles the StateGraph.  Returns the compiled object so
    callers can invoke it with ``graph.invoke(initial_state)``.

``build_graph`` is idempotent and cheap (no I/O).  It can be called once at
module import time or on every test invocation.

LangGraph version notes
-----------------------
Targeting langgraph==1.2.x.  The ``StateGraph`` / ``CompiledStateGraph`` API
has been stable since 0.3.x.  If a future version renames the compiled type,
the only change needed is here, not in nodes.py.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from reconmind.platform_.nodes import (
    action_node,
    intake_node,
    retrieval_node,
)
from reconmind.platform_.state import GraphState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node name constants — used as string keys in the graph.
# Separate from agent_id constants in nodes.py; these are graph vertex labels.
# ---------------------------------------------------------------------------
NODE_INTAKE: str = "intake"
NODE_RETRIEVAL: str = "retrieval"
NODE_ACTION: str = "action"


def build_graph() -> CompiledStateGraph:
    """
    Construct and compile the reconmind LangGraph StateGraph.

    Wires three nodes in a fixed linear sequence::

        START → intake → retrieval → action → END

    Each node is already wrapped with ``@logged_node`` in ``nodes.py``, so
    no extra logging configuration is needed here.

    Returns:
        A compiled ``CompiledStateGraph`` ready to invoke with
        ``graph.invoke(initial_state: GraphState)``.

    Example::

        graph = build_graph()
        final_state = graph.invoke(initial_state)
    """
    builder: StateGraph = StateGraph(GraphState)

    # Register nodes
    builder.add_node(NODE_INTAKE, intake_node)
    builder.add_node(NODE_RETRIEVAL, retrieval_node)
    builder.add_node(NODE_ACTION, action_node)

    # Wire edges: linear sequence
    builder.add_edge(START, NODE_INTAKE)
    builder.add_edge(NODE_INTAKE, NODE_RETRIEVAL)
    builder.add_edge(NODE_RETRIEVAL, NODE_ACTION)
    builder.add_edge(NODE_ACTION, END)

    compiled: CompiledStateGraph = builder.compile()
    logger.debug(
        "Graph compiled: %s → %s → %s",
        NODE_INTAKE, NODE_RETRIEVAL, NODE_ACTION,
    )
    return compiled
