"""Model registry: models.yaml entries -> availability + client callables.

Three adapters cover every provider:
  openai_compat -> openai SDK at base_url (local ollama, OpenAI, OpenRouter, gateways)
  anthropic     -> anthropic SDK (needs ANTHROPIC_API_KEY)
  claude_cli    -> shells out to the `claude` CLI, which authenticates via the Claude
                   Code subscription (CLAUDE_CODE_OAUTH_TOKEN headless, keychain
                   interactively) — no API key. Used for the escalator tier.
A client is a callable verdict(system, user) -> raw model text (expected JSON).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

import yaml

Client = Callable[[str, str], str]


def load_model_configs(path) -> list[dict]:
    return yaml.safe_load(Path(path).read_text())["models"]


def available_models(configs: list[dict], only=None) -> list[tuple[dict, bool]]:
    """Pair each config with whether it is usable (key present / CLI on PATH)."""
    out = []
    for cfg in configs:
        if only and cfg["name"] not in only:
            continue
        if cfg.get("provider") == "claude_cli":
            ok = shutil.which("claude") is not None
        else:
            key_env = cfg.get("api_key_env")
            ok = not key_env or bool(os.environ.get(key_env))
        out.append((cfg, ok))
    return out


def _extract_json(text: str) -> str:
    """First `{...}` block in CLI output, else the raw text (let the parser reject it)."""
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if 0 <= start < end else text


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

    if provider == "claude_cli":
        model = config["model"]
        timeout = config.get("timeout", 120)

        def verdict(system: str, user: str) -> str:
            # No json-mode over the CLI; the prompt carries the "respond ONLY as JSON"
            # contract and _extract_json trims any stray prose. Non-zero exit (e.g. auth
            # failure) raises so get_verdict records it instead of silently going unsure.
            proc = subprocess.run(
                ["claude", "-p", f"{system}\n\n{user}",
                 "--model", model, "--output-format", "text"],
                capture_output=True, text=True, timeout=timeout)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or f"claude exited {proc.returncode}")
            return _extract_json(proc.stdout.strip())
        return verdict

    raise ValueError(f"unknown provider: {provider}")
