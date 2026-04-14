"""
Vanilla sidecar configuration.

Manages paths, LLM settings, and runtime config.
All paths are normalized to forward slashes for cross-platform compatibility.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


def _default_data_dir() -> Path:
    """Return the platform-appropriate app data directory."""
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/Library/Application Support")
    return Path(base) / "vanilla"


@dataclass
class LLMConfig:
    provider: str = "openai"  # openai | anthropic | openrouter | ollama
    api_key: str = ""
    base_url: Optional[str] = None  # for Ollama: http://localhost:11434
    models: dict = field(default_factory=lambda: {
        "ingest": "gpt-4o-mini",
        "analysis": "gpt-4o-mini",
        "proposal": "gpt-4o",
        "fileback": "gpt-4o-mini",
    })
    max_tokens_per_run: int = 20000


@dataclass
class VanillaConfig:
    clean_vault_path: Optional[str] = None
    wiki_vault_path: Optional[str] = None
    data_dir: Path = field(default_factory=_default_data_dir)
    llm: LLMConfig = field(default_factory=LLMConfig)
    initialized: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "vanilla.db"

    @property
    def config_file(self) -> Path:
        return self.data_dir / "config.json"

    def save(self) -> None:
        """Persist config to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "clean_vault_path": self.clean_vault_path,
            "wiki_vault_path": self.wiki_vault_path,
            "initialized": self.initialized,
            "llm": {
                "provider": self.llm.provider,
                "api_key": self.llm.api_key,
                "base_url": self.llm.base_url,
                "models": self.llm.models,
                "max_tokens_per_run": self.llm.max_tokens_per_run,
            },
        }
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls) -> "VanillaConfig":
        """Load config from disk, or return defaults."""
        config = cls()
        if config.config_file.exists():
            with open(config.config_file) as f:
                data = json.load(f)
            config.clean_vault_path = data.get("clean_vault_path")
            config.wiki_vault_path = data.get("wiki_vault_path")
            config.initialized = data.get("initialized", False)
            llm_data = data.get("llm", {})
            config.llm = LLMConfig(
                provider=llm_data.get("provider", "openai"),
                api_key=llm_data.get("api_key", ""),
                base_url=llm_data.get("base_url"),
                models=llm_data.get("models", LLMConfig().models),
                max_tokens_per_run=llm_data.get("max_tokens_per_run", 20000),
            )
        return config
