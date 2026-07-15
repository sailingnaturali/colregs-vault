"""CLI: uv run --group audit python -m audit --models qwen2.5:72b,gpt-4o

Every run scores the jury on the regression corpus first, derives per-model weights from
those scores, and refuses to proceed (exit 1) if the weighted jury regressed on any known
bug. Then it judges all citations, escalates flagged rows to the strong tier, and writes a
weighted, risk-ranked report.
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

from audit.bench import regressions, run_corpus, weights_from_scores
from audit.checks import build_checks
from audit.jury import escalate, run_jury
from audit.models import available_models, load_model_configs, make_client
from audit.report import WEIGHTED_THRESHOLD, _flagged, _key, render

_ROOT = Path(__file__).resolve().parent.parent


def _build_clients(configs, wanted):
    """Split available models into jury (default tier) and escalators (escalate: true)."""
    jury, escalators = {}, {}
    for cfg, ok in available_models(configs, None):
        name = cfg["name"]
        if not ok:
            print(f"skip {name}: {cfg.get('api_key_env')} not set")
            continue
        if cfg.get("escalate"):
            escalators[name] = make_client(cfg)
        elif not wanted or name in wanted:
            jury[name] = make_client(cfg)
    return jury, escalators


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default="",
                    help="comma-separated jury model names (default: all available non-escalators)")
    ap.add_argument("--vault-root", type=Path, default=_ROOT)
    ap.add_argument("--models-config", type=Path, default=_ROOT / "audit" / "models.yaml")
    args = ap.parse_args()

    wanted = {m.strip() for m in args.models.split(",") if m.strip()}
    configs = load_model_configs(args.models_config)
    known = {c["name"] for c in configs}
    for name in wanted - known:
        print(f"warning: --models '{name}' matches no entry in models.yaml")

    jury, escalators = _build_clients(configs, wanted)
    if not jury:
        raise SystemExit("no available jury models — check keys / --models filter")

    # 1. Score jury (+ escalators) on the corpus, derive weights, gate on regression.
    all_clients = {**jury, **escalators}
    scores, table = run_corpus(all_clients, args.vault_root)
    weights = weights_from_scores(scores)
    print("weights: " + ", ".join(f"{n}={weights[n]:.2f}" for n in all_clients))
    regressed = regressions(table, weights, WEIGHTED_THRESHOLD)
    if regressed:
        print(f"\nREGRESSION: weighted jury now gets {len(regressed)} corpus case(s) wrong:")
        for item, expected, _v in regressed:
            print(f"  - {item.row_id} → {item.citation} (expected {expected})")
        sys.exit(1)
    print("corpus: no regression\n")

    # 2. Judge every citation with the routine (cheap) jury.
    items = build_checks(args.vault_root)
    print(f"{len(items)} checks × {len(jury)} jurors: {', '.join(jury)}"
          + (f" · escalators: {', '.join(escalators)}" if escalators else " · no escalator"))
    results = run_jury(items, jury)

    # 3. Escalate only the flagged/split rows to the strong tier.
    escalations = {}
    if escalators:
        for item, verdicts in results:
            if _flagged(verdicts):
                escalations[_key(item)] = escalate(item, verdicts, escalators)
        print(f"escalated {len(escalations)} flagged row(s) to the strong tier")

    date = datetime.date.today().isoformat()
    out = args.vault_root / "audit" / "reports" / f"{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(results, list(jury), date, weights, escalations))
    flagged = sum(1 for _i, v in results if _flagged(v))
    print(f"wrote {out} — {flagged} rows flagged")


if __name__ == "__main__":
    main()
