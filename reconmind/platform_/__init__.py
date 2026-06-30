"""
reconmind.platform_ — platform sub-package init (Milestone 2).

Public re-exports for the most commonly used symbols so callers can write:

    from reconmind.platform_ import build_graph, GraphState

instead of navigating the internal module hierarchy.
"""

from reconmind.platform_.graph import build_graph
from reconmind.platform_.state import GraphState

__all__ = ["build_graph", "GraphState"]
