"""
reconmind.llm.factory
=====================
Factory for instantiating LLMClients based on config.
"""

from reconmind.config import cfg
from reconmind.llm.base import LLMClient
from reconmind.llm.ollama_client import OllamaClient


def get_llm_client(role: str) -> LLMClient:
    """
    Return an LLMClient configured for the specified role.
    
    Reads from cfg.llm.provider and cfg.llm.roles.
    """
    role_cfg = cfg.llm.role(role)
    provider = cfg.llm.provider
    
    if provider == "ollama":
        return OllamaClient(
            base_url=cfg.llm.ollama_base_url,
            model=role_cfg.model,
            temperature=role_cfg.temperature,
        )
    elif provider == "openai":
        # Placeholder for future milestone
        raise NotImplementedError("OpenAI provider not yet implemented.")
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
