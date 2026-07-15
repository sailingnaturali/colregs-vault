"""Score models on the regression corpus — the spine of the self-improving harness.

The corpus (`audit/regression-corpus.yaml`) holds real bugs the vault already fixed:
`wrong` rows a good juror must catch, `correct` rows it must not flag. Scoring it yields
three things every session needs:
  - per-model **weights** for the jury (reliable jurors count more) — see run_jury/report
  - the **regression gate** (does the weighted jury still get every corpus case right?)
  - the **adopt verdict** for a candidate model (`--candidate`)

    uv run --group audit python -m audit.bench --models llama3.3,qwen2.5:72b
    uv run --group audit python -m audit.bench --models qwen2.5:72b --candidate gpt-4o
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from audit.checks import build_checks
from audit.jury import get_verdict
from audit.models import available_models, load_model_configs, make_client
from audit.refs import load_rule_prose

_HERE = Path(__file__).resolve().parent
CORPUS_PATH = _HERE / "regression-corpus.yaml"
WEIGHT_FLOOR = 0.1  # ponytail: no juror fully silenced; a weak model still gets a small say


def load_corpus(path=CORPUS_PATH) -> tuple[list, list]:
    """Return (correct, wrong) as lists of (row_id, citation) tuples."""
    data = yaml.safe_load(Path(path).read_text())
    correct = [(c["row_id"], c["citation"]) for c in data.get("correct", [])]
    wrong = [(w["row_id"], w["citation"]) for w in data.get("wrong", [])]
    return correct, wrong


# Module-level names kept for back-compat with callers/tests.
CORRECT, WRONG = load_corpus()


@dataclass
class BenchScore:
    n_ok: int          # corpus 'correct' cases seen
    n_wrong: int       # corpus 'wrong' cases seen
    false_pos: int     # 'correct' cases the model flagged wrong
    caught: int        # 'wrong' cases the model caught

    @property
    def catch_rate(self) -> float:
        return self.caught / self.n_wrong if self.n_wrong else 1.0

    @property
    def fp_rate(self) -> float:
        return self.false_pos / self.n_ok if self.n_ok else 0.0

    @property
    def weight(self) -> float:
        # ponytail: linear reliability score, floored. Tune the mix if the bench grows.
        raw = 0.5 * self.catch_rate + 0.5 * (1.0 - self.fp_rate)
        return max(WEIGHT_FLOOR, raw)


def bench_cases(vault_root) -> list[tuple]:
    """Return (CheckItem, expected_verdict) pairs for the labeled corpus."""
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


def run_corpus(clients: dict, vault_root) -> tuple[dict, list]:
    """Judge every corpus case with every client.

    Returns (scores, table) where scores is {name: BenchScore} and table is
    [(item, expected, {name: verdict})] — reused for both weights and the regression gate,
    so no corpus case is judged twice.
    """
    cases = bench_cases(vault_root)
    table = [(item, expected, {n: get_verdict(fn, item) for n, fn in clients.items()})
             for item, expected in cases]
    scores = {}
    for name in clients:
        n_ok = n_wrong = fp = caught = 0
        for _item, expected, verdicts in table:
            got = verdicts[name]["verdict"]
            if expected == "ok":
                n_ok += 1
                fp += got != "ok"
            else:
                n_wrong += 1
                caught += got == "wrong"
        scores[name] = BenchScore(n_ok, n_wrong, fp, caught)
    return scores, table


def weights_from_scores(scores: dict) -> dict:
    return {name: s.weight for name, s in scores.items()}


def regressions(table: list, weights: dict, threshold: float) -> list:
    """Corpus cases the *weighted jury* now gets wrong (its collective call flips)."""
    out = []
    for item, expected, verdicts in table:
        wrong_score = sum(weights.get(m, 1.0) * v["confidence"]
                          for m, v in verdicts.items() if v["verdict"] == "wrong")
        if (wrong_score >= threshold) != (expected == "wrong"):
            out.append((item, expected, verdicts))
    return out


def adopt_verdict(candidate: BenchScore, jury_scores: dict) -> tuple[str, str]:
    """Compare a candidate's weight to the current jury median → (verdict, rationale)."""
    weights = sorted(s.weight for s in jury_scores.values())
    if not weights:
        return "adopt", "no existing jury to compare against"
    median = weights[len(weights) // 2]
    w = candidate.weight
    detail = (f"weight {w:.2f} vs jury median {median:.2f} "
              f"(catch {candidate.catch_rate:.0%}, false-pos {candidate.fp_rate:.0%})")
    if w >= median:
        return "adopt", detail
    if w >= 0.8 * median:
        return "probation", detail
    return "reject", detail


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", required=True, help="comma-separated jury model names")
    ap.add_argument("--candidate", default="",
                    help="score this model against the jury and print an adopt verdict")
    ap.add_argument("--vault-root", type=Path, default=_HERE.parent)
    args = ap.parse_args()

    jury_names = [m.strip() for m in args.models.split(",") if m.strip()]
    wanted = jury_names + ([args.candidate] if args.candidate else [])
    configs = load_model_configs(_HERE / "models.yaml")
    clients = {}
    for cfg, ok in available_models(configs, wanted):
        if ok:
            clients[cfg["name"]] = make_client(cfg)
        else:
            print(f"{cfg['name']}: skipped ({cfg.get('api_key_env')} not set)")
    if not clients:
        raise SystemExit("no available models")

    scores, _table = run_corpus(clients, args.vault_root)
    print(f"corpus: {len(CORRECT)} correct + {len(WRONG)} wrong\n")
    for name in clients:
        s = scores[name]
        print(f"{name}: weight {s.weight:.2f} | caught {s.caught}/{s.n_wrong} | "
              f"false-pos {s.false_pos}/{s.n_ok}")

    if args.candidate and args.candidate in scores:
        jury_scores = {n: scores[n] for n in jury_names if n in scores}
        verdict, detail = adopt_verdict(scores[args.candidate], jury_scores)
        print(f"\n=> {args.candidate}: {verdict.upper()} — {detail}")


if __name__ == "__main__":
    main()
