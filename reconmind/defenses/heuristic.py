"""
reconmind.defenses.heuristic
============================
Heuristic (regex/keyword) defense.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict

from reconmind.defenses.base import Defense, DefenseResult

_PATTERN_FILE = Path(__file__).parent / "pattern_library.json"

class HeuristicDefense(Defense):
    def __init__(self):
        with _PATTERN_FILE.open("r") as f:
            self.patterns = json.load(f)
            
    def check(self, text: str, context: Dict[str, Any]) -> DefenseResult:
        t0 = time.time()
        
        lower_text = text.lower()
        matches = []
        
        for category, keyword_list in self.patterns.items():
            for kw in keyword_list:
                if kw.lower() in lower_text:
                    matches.append(kw)
                    
        latency_ms = (time.time() - t0) * 1000.0
        
        triggered = len(matches) > 0
        
        # Simple confidence: capped at 1.0 based on number of matches
        confidence = min(len(matches) * 0.4, 1.0) if triggered else 0.0
        
        reason = f"Matched keywords: {', '.join(matches)}" if triggered else "No heuristic match"
        
        return DefenseResult(
            triggered=triggered,
            confidence=confidence,
            reason=reason,
            latency_ms=latency_ms
        )
