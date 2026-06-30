"""
reconmind.llm.base
==================
Abstract interface for all LLM providers.
"""

import abc
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    text: str
    model_name: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    latency_ms: float
    temperature: float


class LLMClient(abc.ABC):
    """Abstract interface for LLM clients."""

    @abc.abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:
        """
        Generate a response given a system and user prompt.
        
        Args:
            system_prompt: The system instruction.
            user_prompt: The user input.
            
        Returns:
            An LLMResponse containing the output text and metadata.
        """
        pass
