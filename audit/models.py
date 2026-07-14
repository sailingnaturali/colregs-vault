"""Model registry: models.yaml entries -> availability + client callables.

Two adapters cover every provider:
  openai_compat -> openai SDK at base_url (local ollama, OpenAI, OpenRouter, gateways)
  anthropic     -> anthropic SDK
A client is a callable verdict(system, user) -> raw model text (expected JSON).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import yaml

Client = Callable[[str, str], str]


def load_model_configs(path) -> list[dict]:
    return yaml.safe_load(Path(path).read_text())["models"]


def available_models(configs: list[dict], only=None) -> list[tuple[dict, bool]]:
    """Pair each config with whether it is usable (key present, or none required)."""
    out = []
    for cfg in configs:
        if only and cfg["name"] not in only:
            continue
        key_env = cfg.get("api_key_env")
        ok = not key_env or bool(os.environ.get(key_env))
        out.append((cfg, ok))
    return out


def make_client(config: dict) -> Client:
    provider = config["provider"]
    if provider == "openai_compat":
        from openai import OpenAI
        key = os.environ.get(config.get("api_key_env", ""), "") or "ollama"
        client = OpenAI(base_url=config["base_url"], api_key=key)
        model = config["model"]

        def verdict(system: str, user: str) -> str:
            resp = client.chat.completions.create(
                model=model, temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}])
            return resp.choices[0].message.content or ""
        return verdict

    if provider == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ[config["api_key_env"]])
        model = config["model"]

        def verdict(system: str, user: str) -> str:
            resp = client.messages.create(
                model=model, max_tokens=1024, temperature=0,
                system=system, messages=[{"role": "user", "content": user}])
            return resp.content[0].text
        return verdict

    raise ValueError(f"unknown provider: {provider}")
