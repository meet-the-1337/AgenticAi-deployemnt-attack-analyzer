"""
reconmind.defenses.defense_factory
==================================
Factory for instantiating the active defense mechanism.
"""

from typing import Any, Dict
from reconmind.defenses.base import Defense, DefenseResult
from reconmind.defenses.heuristic import HeuristicDefense
from reconmind.defenses.judge_defense import JudgeDefense

class NoOpDefense(Defense):
    def check(self, text: str, context: Dict[str, Any]) -> DefenseResult:
        return DefenseResult(triggered=False, confidence=0.0, reason="Defense disabled", latency_ms=0.0)

def get_defense(cfg: Any) -> Defense:
    active = getattr(cfg.defense, "active", "none").lower()
    
    if active == "heuristic":
        return HeuristicDefense()
    elif active == "judge":
        # Extract threshold if available, otherwise default to 0.7
        threshold = 0.7
        if hasattr(cfg.defense, "judge") and hasattr(cfg.defense.judge, "confidence_threshold"):
            threshold = cfg.defense.judge.confidence_threshold
        return JudgeDefense(confidence_threshold=threshold)
    else:
        return NoOpDefense()
