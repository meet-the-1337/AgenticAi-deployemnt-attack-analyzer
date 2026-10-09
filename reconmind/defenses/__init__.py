"""
reconmind.defenses
==================
Defense mechanisms.
"""

from reconmind.defenses.base import DefenseResult, Defense
from reconmind.defenses.heuristic import HeuristicDefense

__all__ = [
    "DefenseResult",
    "Defense",
    "HeuristicDefense"
]
