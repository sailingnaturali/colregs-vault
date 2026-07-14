from pathlib import Path

from audit.models import load_model_configs, available_models

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
