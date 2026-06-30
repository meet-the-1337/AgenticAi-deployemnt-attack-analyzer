"""
reconmind.llm.ollama_client
===========================
Ollama implementation of LLMClient.
"""

import logging
import time
from typing import Any, Dict

import httpx

from reconmind.llm.base import LLMClient, LLMResponse

logger = logging.getLogger(__name__)


class OllamaClient(LLMClient):
    """Client for local Ollama server."""

    def __init__(self, base_url: str, model: str, temperature: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.client = httpx.Client(timeout=120.0)

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }

        t0 = time.monotonic()
        
        try:
            response = self.client.post(url, json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            logger.warning(f"Ollama request timed out, retrying once: {e}")
            # simple retry once on timeout
            t0 = time.monotonic()
            response = self.client.post(url, json=payload)
            response.raise_for_status()
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to Ollama at {self.base_url}: {e}")
            raise RuntimeError(f"Ollama connection failed: {e}") from e

        t1 = time.monotonic()
        latency_ms = (t1 - t0) * 1000.0

        data: Dict[str, Any] = response.json()
        
        text = data.get("message", {}).get("content", "")
        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")
        
        # Real model name might contain tag, fallback to requested if missing
        model_used = data.get("model", self.model)

        return LLMResponse(
            text=text,
            model_name=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            temperature=self.temperature,
        )
