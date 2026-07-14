"""Score a model on a small known-answer bench — a model-picker for the jury.

Correct cases (expect 'ok') are rows verified against the rule text. Wrong cases
(expect 'wrong') corrupt a citation back to a real bug the vault already fixed, so a
useful juror must flag them. A good model scores high on both: few false positives on
the correct rows AND catches the corrupted ones. Run:

    uv run --group audit python -m audit.bench --models llama3.3,mixtral,qwen2.5:72b
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from audit.checks import build_checks
from audit.jury import get_verdict
from audit.models import available_models, load_model_configs, make_client
from audit.refs import load_rule_prose

# Rows verified correct against the rule text — a juror should return "ok".
CORRECT = [
    ("being-towed-day-over-200m", "Rule 24(e)(iii)"),
    ("fishing-day", "Rule 26(c)(i)"),
    ("motorsailing-night", "Rule 23(a)(i)"),
    ("sailing-under-20m-night", "Rule 25(a)"),
    ("anchored-under-50m-night", "Rule 30(b)"),
    ("aground-day", "Rule 30(d)(ii)"),
]
# (row_id, corrupted_citation) — each is a real bug the vault fixed; expect "wrong".
WRONG = [
    ("being-towed-day-over-200m", "Rule 24(e)(ii)"),   # (ii) is the sternlight, not the diamond
    ("fishing-hauling-night", "Annex II 2(b)"),        # 2(b) is pair-trawling, not hauling
    ("anchored-under-50m-night", "Rule 30(a)"),        # 30(a) is the two-light rig, not one light
    ("towing-masthead-3-night", "Rule 24(c)"),         # 24(c) is pushing/alongside, not a 3-light tow
]


def bench_cases(vault_root) -> list[tuple]:
    """Return (CheckItem, expected_verdict) pairs for the labeled bench."""
    by = {(i.row_id, i.citation): i for i in build_checks(vault_root)}
    cases = []
    for rid, cite in CORRECT:
        item = by.get((rid, cite))
        if item:
            cases.append((item, "ok"))
    for rid, bad in WRONG:
        base = next((i for i in by.values() if i.row_id == rid), None)
        if base:
            corrupted = replace(base, citation=bad,
                                rule_prose=load_rule_prose(vault_root, bad))
            cases.append((corrupted, "wrong"))
    return cases


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", required=True, help="comma-separated model names")
    ap.add_argument("--vault-root", type=Path,
                    default=Path(__file__).resolve().parent.parent)
    args = ap.parse_args()
    only = [m.strip() for m in args.models.split(",") if m.strip()]
    configs = load_model_configs(Path(__file__).resolve().parent / "models.yaml")
    cases = bench_cases(args.vault_root)
    n_ok = sum(1 for _, e in cases if e == "ok")
    n_wrong = sum(1 for _, e in cases if e == "wrong")
    print(f"bench: {n_ok} correct (expect ok) + {n_wrong} corrupted (expect wrong)\n")
    for cfg, available in available_models(configs, only):
        if not available:
            print(f"{cfg['name']}: skipped ({cfg.get('api_key_env')} not set)\n")
            continue
        client = make_client(cfg)
        rows = [(it.row_id, it.citation, exp, get_verdict(client, it)["verdict"])
                for it, exp in cases]
        hits = sum(1 for _r, _c, e, g in rows if e == g)
        false_pos = sum(1 for _r, _c, e, g in rows if e == "ok" and g != "ok")
        caught = sum(1 for _r, _c, e, g in rows if e == "wrong" and g == "wrong")
        print(f"{cfg['name']}: {hits}/{len(rows)} correct | "
              f"false-positives {false_pos}/{n_ok} | caught {caught}/{n_wrong}")
        for rid, cite, exp, got in rows:
            print(f"    {'PASS' if exp == got else 'MISS'}  {rid} {cite}  "
                  f"expect {exp} got {got}")
        print()


if __name__ == "__main__":
    main()
