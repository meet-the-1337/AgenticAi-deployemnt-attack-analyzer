"""
reconmind.defenses.base
=======================
Abstract Base Class for defenses.
"""

import abc
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class DefenseResult:
    triggered: bool
    confidence: float
    reason: str
    latency_ms: float

class Defense(abc.ABC):
    @abc.abstractmethod
    def check(self, text: str, context: Dict[str, Any]) -> DefenseResult:
        """
        Check if the given text and context contain malicious instructions.
        """
        pass
