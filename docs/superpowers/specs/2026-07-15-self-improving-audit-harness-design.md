# Self-improving COLREGS audit harness — design

**Date:** 2026-07-15
**Status:** approved, implementing

## Context

`audit/` already verifies every citation in `requirements.yaml` / `sightings.yaml`
against the **actual rule prose** (`rules/international/*.md`) via a model jury — not
model memory. Reports land in `audit/reports/`. This spec closes the four gaps between
that harness and a self-improving compliance auditor. It is additive; nothing is rebuilt.

The bench is the spine: per-model reliability scores drive juror weights (#1), escalation
targeting (#2), and the adopt verdict (#6).

### Rejected assumption

The original ask was to *hardcode a down-weight on gpt-4o for doctrine*. The 2026-07-14
report shows the opposite: on all three consensus-wrong rows gpt-4o was **right** and the
two local models were both wrong. A fixed prior would have suppressed the correct juror.
Weights are therefore **measured from the regression corpus**, never hand-set.

## Changes

### 1. Regression corpus as data (`audit/regression-corpus.yaml`) — was #5
Move `bench.py`'s `CORRECT` / `WRONG` lists into YAML (`correct:` rows expect `ok`,
`wrong:` rows carry a `why` and expect `wrong` — each is a real bug the vault fixed).
Grown by hand on confirmed-and-fixed bugs only; auto-appending unverified flags would
poison it. `bench.py` loads it, preserving the `CORRECT`/`WRONG` module names.

### 2. Data-driven weights (`bench.py`) — was #1
`BenchScore` per model: `weight = ½·catch_rate + ½·(1−false_positive_rate)`, floored at
`0.1` so no juror is silenced. `// ponytail:` linear combo, tune later.

### 3. Corpus run + regression gate every session (`__main__.py`) — was #5
Score the jury on the corpus first (one call per case per model — reused for weights).
The **weighted jury** must still flag every `wrong` case and pass every `correct` case;
any mismatch → loud "Regression" section + **exit 1**. No extra model calls.

### 4. Escalation tiebreak (`jury.py`, `models.yaml`) — was #2
`models.yaml` entries gain optional `escalate: true` (the strong tier, e.g. Claude).
Escalators are **held out** of the routine jury and run **only on flagged/split rows** —
cheap locals judge all 72 rows, the expensive model judges the handful in dispute. Its
verdict resolves the row: confirm (→ top bucket) or clear (→ downgraded).

### 5. Weighted, escalation-aware report (`report.py`) — was #1 + #3 + ranking
Section order:
1. **Escalation-confirmed** — flagged rows the strong tier calls wrong. Highest risk.
2. **Consensus concerns** (≥2 jurors wrong) minus #1, ranked by weighted risk.
3. **Single-model flags** minus #1, ranked by weighted risk.
4. **Blind spots** — unanimous-`ok` rows ranked by *ascending* mean weighted confidence
   ("everyone agreed, nobody was sure"). `// ponytail:` low-confidence-consensus is the
   cheap proxy for shared bias; family-diversity scoring is the upgrade path.
5. **Model agreement** — per-model tallies + bench weight.

Risk of a row = Σ over wrong-voters of `weight × self-confidence`. Section split stays
count-based (robust, explainable); weights drive **ranking** and the displayed risk.

### 6. Adopt verdict (`bench.py --candidate <model>`) — was #6
Score a candidate against the current jury's median weight → **adopt / probation /
reject**, with the numbers.

## Tests
Extend the existing per-module test files (`test_audit_bench.py`, `test_audit_report.py`,
`test_audit_jury.py`) with pure-function asserts on synthetic verdict dicts — no model
calls. Cover: weight math + floor, regression detection (jury flips a corpus case),
escalation reuse-vs-call, blind-spot ordering, adopt-verdict thresholds.

## Non-goals
Auto-growing the corpus; family-diversity blind-spot scoring; changing the citation-vs-prose
core (it already does exactly what's wanted).
