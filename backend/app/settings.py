"""Load settings.json (and the API key from backend/.env) into a config object."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from app.policy import Policy

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
ENV_FILE = CONFIG_DIR.parent / ".env"
LLM_PROVIDERS = ("ollama", "api")


@dataclass(frozen=True)
class Settings:
    checkpoint: Path
    final_config: Path
    data_dir: Path
    app_data_dir: Path
    port: int
    ollama_url: str
    llm_model: str
    llm_think: bool
    agent_few_shot: bool
    agent_drop_notice_rule: bool
    llm_think_user: bool
    temperature: float
    # Hosted LLM over an OpenAI-compatible API; used when llm_provider is "api".
    llm_provider: str = "ollama"
    api_base_url: str = ""
    api_model: str = ""
    api_reasoning_effort: str | None = None
    api_temperature: float | None = None
    api_key: str = field(default="", repr=False)


def load_env_file(path: Path = ENV_FILE) -> None:
    """Read KEY=VALUE lines from backend/.env into the environment.

    Variables already set in the environment win, so a key exported in the shell
    overrides the file. A missing file is fine.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("'").strip('"'))


def load_settings(path: Path | None = None) -> Settings:
    """Read the settings.json file (default backend/config/settings.json)."""
    raw = json.loads((path or CONFIG_DIR / "settings.json").read_text(encoding="utf-8"))
    load_env_file()
    provider = str(raw.get("llm_provider", "ollama"))
    if provider not in LLM_PROVIDERS:
        raise ValueError(f"llm_provider must be one of {LLM_PROVIDERS}, got {provider!r}.")
    api_temperature = raw.get("api_temperature")
    return Settings(
        checkpoint=Path(raw["checkpoint"]),
        final_config=Path(raw["final_config"]),
        data_dir=Path(raw["data_dir"]),
        app_data_dir=Path(raw["app_data_dir"]),
        port=int(raw["port"]),
        ollama_url=str(raw["ollama_url"]),
        llm_model=str(raw["llm_model"]),
        llm_think=bool(raw["llm_think"]),
        agent_few_shot=bool(raw["agent_few_shot"]),
        agent_drop_notice_rule=bool(raw["agent_drop_notice_rule"]),
        llm_think_user=bool(raw["llm_think_user"]),
        temperature=float(raw["temperature"]),
        llm_provider=provider,
        api_base_url=str(raw.get("api_base_url", "")),
        api_model=str(raw.get("api_model", "")),
        api_reasoning_effort=raw.get("api_reasoning_effort") or None,
        api_temperature=None if api_temperature is None else float(api_temperature),
        api_key=os.environ.get("LLM_API_KEY", ""),
    )


def load_policy(path: Path | None = None) -> Policy:
    """Read backend/config/policy.json, ignoring its provenance metadata."""
    raw = json.loads((path or CONFIG_DIR / "policy.json").read_text(encoding="utf-8"))
    return Policy(
        conf_threshold=float(raw["conf_threshold"]),
        strangeness_threshold=float(raw["strangeness_threshold"]),
        knn_k=int(raw["knn_k"]),
        max_images=int(raw["max_images"]),
    )
