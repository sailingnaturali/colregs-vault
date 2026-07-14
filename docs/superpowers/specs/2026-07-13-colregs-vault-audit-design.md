# colregs-vault-audit — a model jury for the curated tables

**Date:** 2026-07-13
**Status:** approved, pending implementation plan

## Problem

The hand-curated decision tables (`requirements.yaml`, `sightings.yaml`) are the
safety-critical, error-prone half of the vault — every bug found in review lived there
(e.g. trawler hauling cited `Annex II 2(b)` instead of `2(a)(ii)`). The generated rule
prose (`rules/*.md`) is deterministic and high-confidence by comparison. Nothing checks
whether a curated row's cited rule actually *supports* that row's light/shape mapping.

We want a small, model-agnostic harness that has a **jury of LLMs** double-check each
curated row against the cited rule prose, and flags disagreements for human review — so
we can drop in different models (local llama via ollama, OpenAI, Anthropic, any gateway)
and keep improving the vault.

## Non-goals (YAGNI — deferred, designed not to block)

- **Gold-set scoring / model scoreboard.** Designed so `gold/labels.yaml` + accuracy
  scoring can drop in later without rework, but not built now.
- **CI gate.** Model output is nondeterministic; do not block merges on it.
- **prose-vs-source checks** (checking `rules/*.md` against real COLREGS). The prose is
  already deterministic-extracted; the curated tables are where errors live.
- **Concurrency**, and **any vault besides colregs**. Add if measured need appears.

## Architecture

New package `audit/` at the vault root. Model SDK dependencies go in an `audit`
dependency-group so the deterministic build install is untouched.

```
audit/
  __init__.py
  __main__.py     # CLI: uv run --group audit python -m audit --models a,b
  refs.py         # rule-reference -> rules/*.md resolver (shared with tests)
  models.py       # provider registry + adapters (openai_compat, anthropic)
  models.yaml     # the drop-in config: one entry per model
  checks.py       # build check items from requirements.yaml + sightings.yaml
  jury.py         # run each item across models, collect structured verdicts
  report.py       # rank + render markdown
  reports/        # dated run outputs (committed artifacts)
```

### Units and responsibilities

- **`refs.py`** — `ref_to_file(citation) -> "rule-24.md" | "annex-2.md" | None` and a
  `load_rule_prose(vault_root, citation) -> str`. Lifted from the resolver already in
  `tests/test_data_files.py`; that test is refactored to import from here so there is a
  single reference parser. Depends on: nothing (stdlib + the rules/ tree).

- **`models.py`** — reads `models.yaml`, returns callable clients. Two adapters:
  - `openai_compat`: the `openai` SDK pointed at `base_url` (local ollama =
    `http://localhost:11434/v1`, OpenAI cloud = default, gateways/OpenRouter = their
    base_url). Key from `api_key_env` (a dummy is fine for ollama).
  - `anthropic`: the `anthropic` SDK. Inert (skipped with a note) when its
    `api_key_env` is unset. Model ids sourced from the `claude-api` skill at build time.
  Each client exposes `verdict(system, user) -> dict`. A model whose endpoint/key is
  unavailable is **skipped with a logged note**, not an error.

- **`checks.py`** — `build_checks(vault_root) -> list[CheckItem]`. One item per distinct
  `(row_id, citation)` pair in `requirements.yaml` and `sightings.yaml` — a row that cites
  the same rule on several lights collapses to one item (dedup, so the jury isn't asked the
  same question twice). `CheckItem{source, row_id, situation, signal_desc, citation, rule_prose}`.
  `rule_prose` via `refs.load_rule_prose`. Depends on: `refs`, `pyyaml`.

- **`jury.py`** — `run_jury(items, clients) -> list[ItemVerdicts]`. For each item × each
  client, sends a strict prompt (see below) at low temperature with a JSON response
  format, parses `{verdict, confidence, reason, suggested_fix}`, one retry on unparseable
  output then falls back to `verdict="unsure"`. Sequential per model. Depends on: `models`.

- **`report.py`** — `render(item_verdicts) -> markdown`. Flags an item if **any** model
  says `wrong` OR models disagree (not unanimous `ok`). Ranks flagged items by
  (#wrong desc, disagreement desc). Shows each model's verdict/reason/suggested_fix per
  flagged row, then a per-model agreement summary table. Never mutates the vault.

- **`__main__.py`** — parse `--models` (default: all available in `models.yaml`),
  `--vault-root`, build checks, run jury, write `reports/<date>.md`, print a summary.

### The prompt

The model receives only the cited rule's prose and the one claim under test:

> System: You verify a single navigation-rules citation. You are given the exact text of
> the cited rule and a claim mapping a vessel situation / observed signal to that citation.
> Decide whether the cited rule (and sub-paragraph) supports the claim. Respond ONLY as
> JSON: `{"verdict":"ok|wrong|unsure","confidence":0-1,"reason":"...","suggested_fix":"<corrected citation or empty>"}`.
> If the cited paragraph does not support the claim, verdict is "wrong" and put the correct
> citation in suggested_fix.
>
> User: RULE TEXT:\n<prose>\n\nCLAIM:\nsituation=<...> signal=<...> cited as <citation>

Giving it *only* the cited prose (not the whole vault) means a wrong citation has nothing
to lean on — directly catching the `2(b)`-vs-`2(a)(ii)` class.

## Data flow

`models.yaml` → clients ┐
`requirements.yaml`+`sightings.yaml`+`rules/*.md` → `build_checks` → items ┐
items × clients → `run_jury` → per-item verdicts → `render` → `reports/<date>.md`

## Error handling

- Missing key / unreachable endpoint for a model → skip that model, note it in the report
  header. A run with zero available models errors clearly.
- Unparseable model output → one retry, then `verdict="unsure"` (surfaced, never silently
  dropped).
- An item whose citation doesn't resolve to a rule file → this is itself a finding
  (dangling ref); recorded as `wrong` with reason "citation does not resolve", no model
  call needed. (Complements the existing `tests/test_data_files.py` guard.)

## Testing

One test file using a **stub client** (no network) that returns canned verdicts keyed by
row: asserts (1) `build_checks` produces the right items from a tiny fixture vault,
(2) `run_jury` + `report` flag a known-wrong row and rank it above a unanimous-ok row,
(3) `refs.ref_to_file` resolves and rejects as its old test did. Live model calls are not
part of the suite.

## Dependencies

`audit` dependency-group: `openai` (covers all openai_compat incl. ollama), `anthropic`
(for the native adapter). `pyyaml` already present. Run:
`uv run --group audit python -m audit --models qwen2.5:72b,gpt-4o`.
