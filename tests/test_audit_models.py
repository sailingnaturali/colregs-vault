from pathlib import Path

from audit import models as models_mod
from audit.models import _extract_json, available_models, load_model_configs

CONFIG = Path(__file__).resolve().parent.parent / "audit" / "models.yaml"


def test_load_configs_returns_named_entries():
    configs = load_model_configs(CONFIG)
    names = {c["name"] for c in configs}
    assert "qwen2.5:72b" in names and "gpt-4o" in names


def test_available_marks_missing_keys(monkeypatch):
    configs = [
        {"name": "local", "provider": "openai_compat",
         "base_url": "http://x/v1", "model": "m"},                 # no key needed
        {"name": "cloud", "provider": "openai_compat",
         "base_url": "http://y/v1", "model": "m", "api_key_env": "AUDIT_TEST_KEY"},
    ]
    monkeypatch.delenv("AUDIT_TEST_KEY", raising=False)
    avail = dict((c["name"], ok) for c, ok in available_models(configs))
    assert avail == {"local": True, "cloud": False}
    monkeypatch.setenv("AUDIT_TEST_KEY", "x")
    avail = dict((c["name"], ok) for c, ok in available_models(configs))
    assert avail["cloud"] is True


def test_only_filter(monkeypatch):
    configs = [
        {"name": "a", "provider": "openai_compat", "base_url": "u", "model": "m"},
        {"name": "b", "provider": "openai_compat", "base_url": "u", "model": "m"},
    ]
    names = [c["name"] for c, _ in available_models(configs, only=["b"])]
    assert names == ["b"]


def test_claude_cli_available_iff_cli_on_path(monkeypatch):
    configs = [{"name": "claude", "provider": "claude_cli", "model": "claude-sonnet-5"}]
    monkeypatch.setattr(models_mod.shutil, "which", lambda _n: "/usr/bin/claude")
    assert available_models(configs)[0][1] is True
    monkeypatch.setattr(models_mod.shutil, "which", lambda _n: None)
    assert available_models(configs)[0][1] is False   # no key env needed, just the CLI


def test_extract_json_trims_prose_around_verdict():
    assert _extract_json('prefix {"verdict":"ok"} trailing') == '{"verdict":"ok"}'
    assert _extract_json('{"a":1}') == '{"a":1}'
    assert _extract_json("no json here") == "no json here"   # let the parser reject it


def test_escalator_config_uses_claude_cli():
    claude = next(c for c in load_model_configs(CONFIG) if c["name"] == "claude")
    assert claude["provider"] == "claude_cli" and claude.get("escalate") is True
    assert "api_key_env" not in claude          # subscription auth, no key
