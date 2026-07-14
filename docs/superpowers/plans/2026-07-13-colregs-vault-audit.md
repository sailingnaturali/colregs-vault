# colregs-vault-audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A small harness where a jury of drop-in models (local llama via ollama, OpenAI, Anthropic, any gateway) verifies each curated `requirements.yaml`/`sightings.yaml` row against its cited rule prose and reports disagreements for human review.

**Architecture:** New `audit/` package at the vault root. `checks.py` builds one check item per distinct (row, citation) from the two YAMLs, loading the cited rule's prose via a shared `refs.py`. `models.py` turns `models.yaml` entries into client callables (one `openai_compat` adapter covers ollama/OpenAI/gateways by base_url; one `anthropic` adapter). `jury.py` runs each item across each client for a structured verdict; `report.py` ranks and renders. Never edits the vault.

**Tech Stack:** Python 3.11+, `openai` SDK (all openai_compat incl. ollama), `anthropic` SDK, `pyyaml`, pytest, uv.

## Global Constraints

- Python `>=3.11`; project is `package = false` (uv), tests via `[tool.pytest.ini_options] pythonpath`.
- Model SDK deps live in a **new `audit` dependency-group**, never in `[project].dependencies`.
- The harness **never mutates the vault**; it only writes `audit/reports/<date>.md`.
- All modules use **absolute imports** (`from audit.x import y`).
- A model whose `api_key_env` is unset is **skipped with a printed note**, not an error.
- Reuse the existing rule-reference resolver — do not write a second citation parser.

---

### Task 1: Shared reference resolver (`audit/refs.py`)

**Files:**
- Create: `audit/__init__.py` (empty)
- Create: `audit/refs.py`
- Test: `tests/test_audit_refs.py`
- Modify: `tests/test_data_files.py` (import the shared resolver instead of its local copy)
- Modify: `pyproject.toml` (add `.` to `pythonpath`)

**Interfaces:**
- Produces: `ref_to_file(citation: str) -> str | None` (e.g. `"Annex II 2(a)(ii)"` → `"annex-2.md"`, `"Rule 24(a)(i)"` → `"rule-24.md"`, unparseable → `None`); `load_rule_prose(vault_root: Path, citation: str, regime: str = "international") -> str | None` (frontmatter-stripped prose, or `None` if the file doesn't exist).

- [ ] **Step 1: Add `.` to pytest pythonpath**

Modify `pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["scripts", "."]
```

- [ ] **Step 2: Create the empty package marker**

Create `audit/__init__.py` with a single line:
```python
"""Model-jury audit harness for the colregs vault."""
```

- [ ] **Step 3: Write the failing test**

Create `tests/test_audit_refs.py`:
```python
from pathlib import Path

from audit.refs import ref_to_file, load_rule_prose

VAULT = Path(__file__).resolve().parent.parent


def test_ref_to_file_maps_rules_and_annexes():
    assert ref_to_file("Rule 24(a)(i)") == "rule-24.md"
    assert ref_to_file("Annex II 2(a)(ii)") == "annex-2.md"
    assert ref_to_file("Rule 30(b)") == "rule-30.md"
    assert ref_to_file("nonsense") is None


def test_load_rule_prose_strips_frontmatter():
    prose = load_rule_prose(VAULT, "Rule 30(b)")
    assert prose is not None
    assert prose.startswith("(a) A vessel at anchor")
    assert "verified:" not in prose          # frontmatter gone


def test_load_rule_prose_missing_file_is_none():
    assert load_rule_prose(VAULT, "Rule 99") is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_audit_refs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'audit.refs'`

- [ ] **Step 5: Write the implementation**

Create `audit/refs.py`:
```python
"""Resolve a COLREGS citation to its rule file and load that file's prose.

Single source of truth for citation parsing — imported by both the audit harness
and tests/test_data_files.py.
"""
from __future__ import annotations

import re
from pathlib import Path

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def ref_to_file(citation: str) -> str | None:
    """'Annex II 2(a)(ii)' -> 'annex-2.md'; 'Rule 24(a)(i)' -> 'rule-24.md'; else None."""
    annex = re.search(r"Annex\s+([IVX]+)", citation)
    if annex:
        return f"annex-{ROMAN[annex.group(1)]}.md"
    num = re.search(r"(\d+)", citation)
    return f"rule-{int(num.group(1)):02d}.md" if num else None


def load_rule_prose(vault_root: Path, citation: str,
                    regime: str = "international") -> str | None:
    """The cited rule's prose with YAML frontmatter stripped, or None if unresolved."""
    filename = ref_to_file(citation)
    if not filename:
        return None
    path = Path(vault_root) / "rules" / regime / filename
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        _, _frontmatter, body = text.split("---", 2)
        return body.strip()
    return text.strip()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_audit_refs.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Refactor test_data_files.py to use the shared resolver**

In `tests/test_data_files.py`, replace the local `ROMAN` dict and `_ref_to_file` function with an import. Change the top imports to add:
```python
from audit.refs import ref_to_file
```
Delete the local `ROMAN = {...}` assignment and the entire `def _ref_to_file(segment): ...` function. Then replace the one call site inside `test_every_rule_reference_resolves` — change `filename = _ref_to_file(segment)` to `filename = ref_to_file(segment)`.

- [ ] **Step 8: Run the full suite to verify nothing broke**

Run: `uv run pytest -q`
Expected: PASS (all existing tests + 3 new)

- [ ] **Step 9: Commit**

```bash
git add audit/__init__.py audit/refs.py tests/test_audit_refs.py tests/test_data_files.py pyproject.toml
git commit -m "feat(audit): shared citation resolver (refs.py)"
```

---

### Task 2: Build check items (`audit/checks.py`)

**Files:**
- Create: `audit/checks.py`
- Test: `tests/test_audit_checks.py`

**Interfaces:**
- Consumes: `audit.refs.load_rule_prose`.
- Produces: `@dataclass CheckItem{source: str, row_id: str, situation: str, signal_desc: str, citation: str, rule_prose: str | None}`; `build_checks(vault_root) -> list[CheckItem]` — one item per distinct `(source, row_id, citation)`; `'Rule 25(e)+23(a)'` splits into two citations; `rule_prose` is `None` for unresolved citations.

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_checks.py`:
```python
from pathlib import Path

from audit.checks import build_checks, CheckItem

VAULT = Path(__file__).resolve().parent.parent


def test_build_checks_covers_both_sources_with_prose():
    items = build_checks(VAULT)
    assert items
    sources = {i.source for i in items}
    assert sources == {"requirements.yaml", "sightings.yaml"}
    # every resolvable citation carries loaded prose
    resolved = [i for i in items if i.rule_prose is not None]
    assert resolved and all(len(i.rule_prose) > 20 for i in resolved)


def test_build_checks_dedups_row_citation_pairs():
    items = build_checks(VAULT)
    keys = [(i.source, i.row_id, i.citation) for i in items]
    assert len(keys) == len(set(keys))          # no duplicate (row, citation)


def test_build_checks_has_known_row():
    items = build_checks(VAULT)
    hauling = [i for i in items
               if i.row_id == "fishing-hauling-night" and "Annex II" in i.citation]
    assert hauling and hauling[0].citation == "Annex II 2(a)(ii)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audit_checks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'audit.checks'`

- [ ] **Step 3: Write the implementation**

Create `audit/checks.py`:
```python
"""Turn the curated decision tables into per-citation check items."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from audit.refs import load_rule_prose


@dataclass
class CheckItem:
    source: str          # "requirements.yaml" | "sightings.yaml"
    row_id: str
    situation: str
    signal_desc: str
    citation: str
    rule_prose: str | None


def _requirements_rows(data):
    """Yield (row_id, situation, signal_desc, ref) from requirements.yaml."""
    for entry in data.get("entries", []):
        rid = entry["id"]
        situation = entry.get("match", {}).get("situation", "")
        lights = list(entry.get("lights", [])) + list(entry.get("shapes", []))
        for opt in entry.get("light_options", []):
            lights += list(opt)
        for light in lights:
            if "rule" in light:
                yield rid, situation, light.get("desc", ""), light["rule"]


def _sightings_rows(data):
    """Yield (row_id, situation, signal_desc, ref) from sightings.yaml."""
    for pat in data.get("patterns", []):
        rid = pat["id"]
        arrangement = "+".join(pat.get("arrangement", []))
        condition = pat.get("condition", "")
        for cand in pat.get("candidates", []):
            note = cand.get("note", "")
            desc = f"{arrangement} [{condition}]: {note}".strip()
            yield rid, cand.get("situation", ""), desc, cand["rule"]


def build_checks(vault_root) -> list[CheckItem]:
    vault_root = Path(vault_root)
    sources = [
        ("requirements.yaml", _requirements_rows),
        ("sightings.yaml", _sightings_rows),
    ]
    items: list[CheckItem] = []
    seen: set[tuple[str, str, str]] = set()
    for name, extractor in sources:
        data = yaml.safe_load((vault_root / name).read_text())
        for rid, situation, signal, ref in extractor(data):
            for citation in (s.strip() for s in ref.split("+")):
                key = (name, rid, citation)
                if key in seen:
                    continue
                seen.add(key)
                items.append(CheckItem(
                    source=name, row_id=rid, situation=situation,
                    signal_desc=signal, citation=citation,
                    rule_prose=load_rule_prose(vault_root, citation)))
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_audit_checks.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add audit/checks.py tests/test_audit_checks.py
git commit -m "feat(audit): build check items from curated tables"
```

---

### Task 3: Model config + availability (`audit/models.py`, `audit/models.yaml`)

**Files:**
- Create: `audit/models.py`
- Create: `audit/models.yaml`
- Test: `tests/test_audit_models.py`

**Interfaces:**
- Produces: `load_model_configs(path) -> list[dict]` (reads the `models:` list); `available_models(configs, only=None) -> list[tuple[dict, bool]]` (`bool` = key present / no key needed; `only` filters by name); `make_client(config) -> Callable[[str, str], str]` — returns a `verdict(system, user) -> raw_json_text` callable. `make_client` is thin and imports its SDK lazily; it is NOT unit-tested (no network in the suite).

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_models.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audit_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'audit.models'`

- [ ] **Step 3: Create the model config**

Create `audit/models.yaml`:
```yaml
# Drop in a model from anywhere by adding an entry.
#   provider: openai_compat  -> the openai SDK pointed at base_url (ollama, OpenAI,
#                               OpenRouter, any gateway). api_key_env optional (ollama
#                               ignores it). Model must serve /v1/chat/completions.
#   provider: anthropic      -> the anthropic SDK; requires api_key_env to be set.
models:
  - name: qwen2.5:72b
    provider: openai_compat
    base_url: http://localhost:11434/v1
    model: qwen2.5:72b
  - name: llama3.1
    provider: openai_compat
    base_url: http://localhost:11434/v1
    model: llama3.1:latest
  - name: gpt-4o
    provider: openai_compat
    base_url: https://api.openai.com/v1
    model: gpt-4o
    api_key_env: OPENAI_API_KEY
  # Inert until ANTHROPIC_API_KEY is set. Confirm the model id via the claude-api skill.
  - name: claude
    provider: anthropic
    model: claude-sonnet-5
    api_key_env: ANTHROPIC_API_KEY
```

- [ ] **Step 4: Write the implementation**

Create `audit/models.py`:
```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_audit_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add audit/models.py audit/models.yaml tests/test_audit_models.py
git commit -m "feat(audit): model registry + openai_compat/anthropic adapters"
```

---

### Task 4: The jury (`audit/jury.py`)

**Files:**
- Create: `audit/jury.py`
- Test: `tests/test_audit_jury.py`

**Interfaces:**
- Consumes: `audit.checks.CheckItem`, a client callable `(system, user) -> str`.
- Produces: `SYSTEM: str`; `build_prompt(item) -> tuple[str, str]`; `parse_verdict(text) -> dict | None`; `get_verdict(client, item, retries=1) -> dict` with keys `verdict` (`ok|wrong|unsure`), `confidence` (float), `reason` (str), `suggested_fix` (str); `run_jury(items, clients: dict[str, Client]) -> list[tuple[CheckItem, dict[str, dict]]]`. An item with `rule_prose is None` yields a canned `wrong` verdict per model WITHOUT calling the client.

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_jury.py`:
```python
from audit.checks import CheckItem
from audit.jury import parse_verdict, get_verdict, run_jury


def _item(prose="(a) some rule text long enough to matter."):
    return CheckItem("sightings.yaml", "row1", "fishing",
                     "white+red [night]", "Annex II 2(a)(ii)", prose)


def test_parse_verdict_normalizes_and_rejects_junk():
    v = parse_verdict('{"verdict":"wrong","confidence":0.9,"reason":"r","suggested_fix":"X"}')
    assert v == {"verdict": "wrong", "confidence": 0.9, "reason": "r", "suggested_fix": "X"}
    assert parse_verdict("not json") is None
    bad = parse_verdict('{"verdict":"maybe"}')          # unknown verdict -> unsure
    assert bad["verdict"] == "unsure"


def test_get_verdict_retries_then_unsure():
    calls = {"n": 0}

    def flaky(system, user):
        calls["n"] += 1
        return "garbage"
    v = get_verdict(flaky, _item(), retries=1)
    assert v["verdict"] == "unsure"
    assert calls["n"] == 2                               # initial + one retry


def test_dangling_citation_is_wrong_without_calling_model():
    called = {"n": 0}

    def never(system, user):
        called["n"] += 1
        return "{}"
    v = get_verdict(never, _item(prose=None))
    assert v["verdict"] == "wrong" and called["n"] == 0


def test_run_jury_collects_per_model_verdicts():
    def ok_client(system, user):
        return '{"verdict":"ok","confidence":1,"reason":"","suggested_fix":""}'

    def wrong_client(system, user):
        return '{"verdict":"wrong","confidence":1,"reason":"bad","suggested_fix":"Y"}'
    results = run_jury([_item()], {"a": ok_client, "b": wrong_client})
    assert len(results) == 1
    _item_out, verdicts = results[0]
    assert verdicts["a"]["verdict"] == "ok"
    assert verdicts["b"]["verdict"] == "wrong"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audit_jury.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'audit.jury'`

- [ ] **Step 3: Write the implementation**

Create `audit/jury.py`:
```python
"""Run each check item across each model client and collect structured verdicts."""
from __future__ import annotations

import json
from typing import Callable

from audit.checks import CheckItem

Client = Callable[[str, str], str]

SYSTEM = (
    "You verify a single navigation-rules citation. You are given the exact text of the "
    "cited rule and a claim mapping a vessel situation / observed signal to that citation. "
    "Decide whether the cited rule — and its specific sub-paragraph — supports the claim. "
    'Respond ONLY as JSON: {"verdict":"ok|wrong|unsure","confidence":0-1,"reason":"...",'
    '"suggested_fix":"<corrected citation, or empty>"}. If the cited paragraph does not '
    'support the claim, verdict is "wrong" and put the correct citation in suggested_fix.'
)

_VERDICTS = {"ok", "wrong", "unsure"}


def build_prompt(item: CheckItem) -> tuple[str, str]:
    prose = item.rule_prose or "(cited rule text not found)"
    user = (f"RULE TEXT:\n{prose}\n\nCLAIM:\nsituation={item.situation} "
            f"signal={item.signal_desc} cited as {item.citation}")
    return SYSTEM, user


def parse_verdict(text: str) -> dict | None:
    try:
        d = json.loads(text)
    except (ValueError, TypeError):
        return None
    verdict = d.get("verdict", "unsure")
    if verdict not in _VERDICTS:
        verdict = "unsure"
    try:
        confidence = float(d.get("confidence", 0) or 0)
    except (ValueError, TypeError):
        confidence = 0.0
    return {"verdict": verdict, "confidence": confidence,
            "reason": str(d.get("reason", "")),
            "suggested_fix": str(d.get("suggested_fix", ""))}


def get_verdict(client: Client, item: CheckItem, retries: int = 1) -> dict:
    if item.rule_prose is None:
        return {"verdict": "wrong", "confidence": 1.0,
                "reason": "citation does not resolve to a rule file", "suggested_fix": ""}
    system, user = build_prompt(item)
    for _ in range(retries + 1):
        parsed = parse_verdict(client(system, user))
        if parsed:
            return parsed
    return {"verdict": "unsure", "confidence": 0.0,
            "reason": "unparseable model output", "suggested_fix": ""}


def run_jury(items, clients: dict[str, Client]):
    results = []
    for item in items:
        verdicts = {name: get_verdict(fn, item) for name, fn in clients.items()}
        results.append((item, verdicts))
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_audit_jury.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add audit/jury.py tests/test_audit_jury.py
git commit -m "feat(audit): jury runner + verdict parsing"
```

---

### Task 5: The report (`audit/report.py`)

**Files:**
- Create: `audit/report.py`
- Test: `tests/test_audit_report.py`

**Interfaces:**
- Consumes: `run_jury` output `list[tuple[CheckItem, dict[str, dict]]]`.
- Produces: `render(results, model_names: list[str], date: str) -> str` (markdown). A row is flagged if any model says `wrong` OR verdicts are not unanimous. Flagged rows sort by (#wrong desc, distinct-verdict-count desc) and appear before a per-model agreement summary.

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_report.py`:
```python
from audit.checks import CheckItem
from audit.report import render


def _item(rid):
    return CheckItem("sightings.yaml", rid, "fishing", "sig", "Annex II 2(a)(ii)", "prose")


def _v(verdict, fix=""):
    return {"verdict": verdict, "confidence": 1.0, "reason": "r", "suggested_fix": fix}


def test_render_flags_and_ranks():
    results = [
        (_item("agree-ok"), {"a": _v("ok"), "b": _v("ok")}),          # not flagged
        (_item("split"), {"a": _v("ok"), "b": _v("wrong", "X")}),      # flagged (disagree)
        (_item("both-wrong"), {"a": _v("wrong", "Y"), "b": _v("wrong", "Y")}),  # flagged
    ]
    out = render(results, ["a", "b"], "2026-07-13")
    assert "agree-ok" not in out.split("## Model agreement")[0]     # unanimous ok omitted
    # both-wrong (2 wrong) ranks above split (1 wrong)
    assert out.index("both-wrong") < out.index("split")
    assert "suggest `X`" in out
    assert "## Model agreement" in out
    assert "2 of 3 rows flagged" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audit_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'audit.report'`

- [ ] **Step 3: Write the implementation**

Create `audit/report.py`:
```python
"""Rank flagged rows and render a markdown audit report."""
from __future__ import annotations


def _flagged(verdicts: dict) -> bool:
    kinds = [v["verdict"] for v in verdicts.values()]
    return any(k == "wrong" for k in kinds) or len(set(kinds)) > 1


def _rank_key(verdicts: dict):
    kinds = [v["verdict"] for v in verdicts.values()]
    return (-sum(1 for k in kinds if k == "wrong"), -len(set(kinds)))


def render(results, model_names: list[str], date: str) -> str:
    flagged = [(item, v) for item, v in results if _flagged(v)]
    flagged.sort(key=lambda iv: _rank_key(iv[1]))

    lines = [f"# colregs-vault audit — {date}", "",
             f"Models: {', '.join(model_names)}", "",
             f"{len(flagged)} of {len(results)} rows flagged for review.", ""]

    for item, verdicts in flagged:
        lines.append(f"## {item.source} · {item.row_id} → `{item.citation}`")
        lines.append(f"_{item.situation} · {item.signal_desc}_")
        for name in model_names:
            v = verdicts[name]
            fix = f" — suggest `{v['suggested_fix']}`" if v["suggested_fix"] else ""
            lines.append(f"- **{name}**: {v['verdict']} "
                         f"({v['confidence']:.2f}) — {v['reason']}{fix}")
        lines.append("")

    lines.append("## Model agreement")
    for name in model_names:
        counts = {"ok": 0, "wrong": 0, "unsure": 0}
        for _item, verdicts in results:
            counts[verdicts[name]["verdict"]] += 1
        lines.append(f"- {name}: ok {counts['ok']}, "
                     f"wrong {counts['wrong']}, unsure {counts['unsure']}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_audit_report.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add audit/report.py tests/test_audit_report.py
git commit -m "feat(audit): report ranking + markdown render"
```

---

### Task 6: CLI entrypoint + dependency group (`audit/__main__.py`, `pyproject.toml`)

**Files:**
- Create: `audit/__main__.py`
- Modify: `pyproject.toml` (add the `audit` dependency-group)

**Interfaces:**
- Consumes: `build_checks`, `load_model_configs`, `available_models`, `make_client`, `run_jury`, `render`.
- Produces: `python -m audit [--models a,b] [--vault-root PATH] [--models-config PATH]` → writes `audit/reports/<YYYY-MM-DD>.md`, prints a summary; exits non-zero if no models are available.

- [ ] **Step 1: Add the audit dependency group**

Modify `pyproject.toml`, adding under `[dependency-groups]`:
```toml
[dependency-groups]
dev = ["pytest>=8"]
audit = ["openai>=1.40", "anthropic>=0.40"]
```

- [ ] **Step 2: Sync the new group**

Run: `uv sync --group audit`
Expected: resolves and installs `openai` and `anthropic`.

- [ ] **Step 3: Write the CLI**

Create `audit/__main__.py`:
```python
"""CLI: uv run --group audit python -m audit --models qwen2.5:72b,gpt-4o"""
from __future__ import annotations

import argparse
import datetime
from pathlib import Path

from audit.checks import build_checks
from audit.jury import run_jury
from audit.models import available_models, load_model_configs, make_client
from audit.report import render

_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default="",
                    help="comma-separated model names (default: all available)")
    ap.add_argument("--vault-root", type=Path, default=_ROOT)
    ap.add_argument("--models-config", type=Path, default=_ROOT / "audit" / "models.yaml")
    args = ap.parse_args()

    only = [m.strip() for m in args.models.split(",") if m.strip()] or None
    configs = load_model_configs(args.models_config)
    clients = {}
    for cfg, ok in available_models(configs, only):
        if not ok:
            print(f"skip {cfg['name']}: {cfg.get('api_key_env')} not set")
            continue
        clients[cfg["name"]] = make_client(cfg)
    if not clients:
        raise SystemExit("no available models — check keys / --models filter")

    items = build_checks(args.vault_root)
    print(f"{len(items)} checks × {len(clients)} models: {', '.join(clients)}")
    results = run_jury(items, clients)

    date = datetime.date.today().isoformat()
    out = args.vault_root / "audit" / "reports" / f"{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(results, list(clients), date))
    flagged = sum(1 for _i, v in results
                  if any(x["verdict"] == "wrong" for x in v.values())
                  or len({x["verdict"] for x in v.values()}) > 1)
    print(f"wrote {out} — {flagged} rows flagged")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify the CLI wiring with the fast local model (smoke)**

Run: `uv run --group audit python -m audit --models llama3.1`
Expected: prints `N checks × 1 models: llama3.1`, then `wrote audit/reports/<date>.md — K rows flagged`. (Requires ollama running; `llama3.1` is the fastest local model for a quick wiring check.)

- [ ] **Step 5: Commit**

```bash
git add audit/__main__.py pyproject.toml uv.lock
git commit -m "feat(audit): CLI entrypoint + audit dependency group"
```

---

### Task 7: Docs + full live run

**Files:**
- Modify: `README.md` (document the audit harness)
- Create: `audit/reports/<date>.md` (committed artifact from the live run)
- Create: `audit/reports/.gitkeep` if the live run is deferred

**Interfaces:** none (documentation + verification task).

- [ ] **Step 1: Document the harness in the README**

Add a section to `README.md` after "Review checklist":
```markdown
## Auditing the curated tables

`audit/` runs a jury of models over every `requirements.yaml` / `sightings.yaml`
citation, checking each against the cited rule's prose and flagging disagreements.
It never edits the vault — it writes a dated report under `audit/reports/`.

```bash
uv run --group audit python -m audit                       # all available models
uv run --group audit python -m audit --models qwen2.5:72b,gpt-4o
```

Add a model from anywhere by editing `audit/models.yaml`: `openai_compat` entries
point the OpenAI SDK at any `base_url` (local ollama, OpenAI, OpenRouter, a gateway);
`anthropic` entries use the Anthropic SDK. A model whose `api_key_env` is unset is
skipped. See `docs/superpowers/specs/2026-07-13-colregs-vault-audit-design.md`.
```

- [ ] **Step 2: Run the full jury live**

Run: `uv run --group audit python -m audit --models qwen2.5:72b,gpt-4o`
Expected: writes `audit/reports/<date>.md`. (Requires ollama up and `OPENAI_API_KEY` set. If `OPENAI_API_KEY` is absent, run `--models qwen2.5:72b,llama3.1` instead and note it.)

- [ ] **Step 3: Sanity-check the report by hand**

Open `audit/reports/<date>.md`. Confirm: flagged rows show per-model verdicts + reasons, the agreement summary lists each model's ok/wrong/unsure counts, and the four known-good citations we already fixed (fishing-hauling → `Annex II 2(a)(ii)`, etc.) are NOT flagged as wrong. Any surprising flag is a real review item — note it for Bryan, do not auto-edit.

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS (all prior tests + the four new audit test files).

- [ ] **Step 5: Commit**

```bash
git add README.md audit/reports/
git commit -m "docs(audit): README + first live jury report"
```

---

## Notes for the implementer

- **Ollama must be running** for local models (`ollama list` to confirm; the endpoint is `http://localhost:11434/v1`). If a local model rejects `response_format={"type":"json_object"}`, its output fails to parse → retried once → recorded `unsure`; that surfaces in the report rather than crashing.
- **Do not** add `openai`/`anthropic` to `[project].dependencies` — they belong only in the `audit` group so the deterministic build stays lean.
- The harness is **advisory**: a `wrong` verdict is a prompt for human review, never an auto-edit. The existing `tests/test_data_files.py` guard remains the deterministic backstop for dangling citations.
