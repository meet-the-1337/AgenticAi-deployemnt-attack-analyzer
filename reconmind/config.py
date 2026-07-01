"""
reconmind.config
================
Single config loader for the entire codebase.

Rules:
  - Import ``cfg`` (the singleton Config object) from here — never call
    yaml.safe_load or os.getenv directly in application code.
  - This module is loaded once at import time; subsequent imports hit the
    module cache.
  - config.yaml is looked up relative to this file's grandparent (repo root),
    so it works regardless of the working directory the script is launched from.

Usage:
    from reconmind.config import cfg
    db_path  = cfg.database.resolved_path
    model    = cfg.llm.role("target_agent").model
    temp     = cfg.llm.role("target_agent").temperature
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator, model_validator

# ---------------------------------------------------------------------------
# Repo root resolution — robust regardless of CWD
# ---------------------------------------------------------------------------
# __file__ is  <repo>/reconmind/reconmind/config.py
# parent       <repo>/reconmind/reconmind/
# parent.parent<repo>/reconmind/          ← repo root (where config.yaml lives)
_REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Pydantic models (nested, typed, validated)
# ---------------------------------------------------------------------------

class DatabaseConfig(BaseModel):
    path: str  # raw value from YAML; resolved to absolute Path via property

    @property
    def resolved_path(self) -> Path:
        """Always returns an absolute Path, anchored at repo root if relative."""
        p = Path(self.path)
        return p if p.is_absolute() else (_REPO_ROOT / p).resolve()


class RoleConfig(BaseModel):
    """Per-role LLM settings (model + temperature).

    This indirection means M8's judge-based defense can point at a different
    model without touching any calling code — just change config.yaml.
    """

    model: str
    temperature: float = 0.7

    @field_validator("temperature")
    @classmethod
    def _temp_range(cls, v: float) -> float:
        if not (0.0 <= v <= 2.0):
            raise ValueError(f"temperature must be in [0.0, 2.0], got {v}")
        return v


class LLMConfig(BaseModel):
    """LLM provider + per-role settings."""

    provider: Literal["openai", "ollama"] = "ollama"
    openai_api_key_env: str = "OPENAI_API_KEY"
    ollama_base_url: str = "http://localhost:11434"

    # Per-role sub-configs.  Keys are role names passed to get_llm_client().
    # A special "default" key is used as fallback when the requested role has
    # no explicit entry.
    roles: dict[str, RoleConfig] = {}

    @field_validator("provider")
    @classmethod
    def _provider_valid(cls, v: str) -> str:
        allowed = {"openai", "ollama"}
        if v not in allowed:
            raise ValueError(f"llm.provider must be one of {allowed}, got '{v}'")
        return v

    def role(self, name: str) -> RoleConfig:
        """
        Return the RoleConfig for ``name``, falling back to ``default`` if the
        role is not explicitly configured.

        Args:
            name: Role name, e.g. ``"target_agent"`` or ``"judge"``.

        Returns:
            RoleConfig for the given role.

        Raises:
            KeyError: if neither ``name`` nor ``"default"`` exists in roles.
        """
        if name in self.roles:
            return self.roles[name]
        if "default" in self.roles:
            return self.roles["default"]
        raise KeyError(
            f"LLM role '{name}' not found in config.yaml and no 'default' role defined. "
            f"Available roles: {list(self.roles.keys())}"
        )


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"

class JudgeDefenseConfig(BaseModel):
    confidence_threshold: float = 0.7

class DefenseConfig(BaseModel):
    active: str = "none"
    blocking: bool = False
    judge: JudgeDefenseConfig = JudgeDefenseConfig()


class Config(BaseModel):
    """Top-level Config object — the only thing the rest of the codebase imports."""

    database: DatabaseConfig
    llm: LLMConfig
    defense: DefenseConfig
    logging: LoggingConfig

    @model_validator(mode="after")
    def _check_db_parent_writable(self) -> "Config":
        """Warn (don't crash) if the DB's parent directory doesn't exist yet."""
        db_parent = self.database.resolved_path.parent
        if not db_parent.exists():
            import warnings
            warnings.warn(
                f"DB directory '{db_parent}' does not exist yet — "
                "init_db.py will create it on first run.",
                stacklevel=2,
            )
        return self


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _load_config(yaml_path: Path | None = None) -> Config:
    """
    Load and validate config.yaml.

    Args:
        yaml_path: Override the default location (useful for tests).

    Returns:
        Validated Config instance.

    Raises:
        FileNotFoundError: if config.yaml is missing.
        pydantic.ValidationError: if required keys are absent or invalid.
    """
    if yaml_path is None:
        yaml_path = _REPO_ROOT / "config.yaml"

    if not yaml_path.exists():
        raise FileNotFoundError(
            f"config.yaml not found at '{yaml_path}'. "
            "Make sure you are running from the repo root or that config.yaml exists."
        )

    with yaml_path.open("r", encoding="utf-8") as fh:
        raw: dict = yaml.safe_load(fh) or {}

    return Config(**raw)


# ---------------------------------------------------------------------------
# Module-level singleton — imported by the rest of the codebase
# ---------------------------------------------------------------------------
cfg: Config = _load_config()
