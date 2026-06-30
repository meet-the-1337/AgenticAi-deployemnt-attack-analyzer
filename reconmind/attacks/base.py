"""
reconmind.attacks.base
======================
Abstract Base Class for all attacks.
"""

import abc
from dataclasses import dataclass
from typing import Any, Dict

from reconmind.platform_.state import GraphState


@dataclass
class AttackConfig:
    attack_type: str
    objective: str
    strength: str
    entry_point: str


class Attack(abc.ABC):
    """
    Abstract base class for all attack vectors.
    """
    
    def __init__(self, config: AttackConfig):
        self.config = config

    @abc.abstractmethod
    def inject(self, initial_state: GraphState) -> GraphState:
        """
        Mutate the initial graph state to inject the attack payload.
        """
        pass

    @abc.abstractmethod
    def expected_signal(self) -> Dict[str, Any]:
        """
        Declare what success looks like for the Oracle in M7.
        Returns a dict of expected behaviors (e.g. {"tool": "escalate_to_admin", "any_args": True}).
        """
        pass
