"""Completeness / sanity checks for a built rule set. Importable so tests and the
data-file guard can reuse it without loading the entry-point script."""
from __future__ import annotations

import re

from .model import RuleDoc

EXPECTED: dict[str, list[str]] = {
    "international": [str(n) for n in range(1, 39)]
                     + ["Annex I", "Annex II", "Annex III", "Annex IV"],
    "inland": [str(n) for n in range(1, 39)]
              + ["Annex I", "Annex II", "Annex III", "Annex IV", "Annex V"],
    "canadian": [str(n) for n in range(1, 47)]
                + ["Annex I", "Annex II", "Annex III", "Annex IV"],
}
_ARTIFACTS = re.compile(r"—CONTINUED|\(continued\)", re.IGNORECASE)


def _is_reserved_stub(d: RuleDoc) -> bool:
    return "reserved" in d.prose[:60].lower()


def validate(docs: list[RuleDoc]) -> list[str]:
    errors: list[str] = []
    by_regime: dict[str, list[RuleDoc]] = {r: [] for r in EXPECTED}
    for d in docs:
        by_regime.setdefault(d.regime, []).append(d)
    for regime, expected in EXPECTED.items():
        got = [d.number for d in by_regime[regime]]
        for n in sorted(set(expected) - set(got)):
            errors.append(f"{regime}: missing {n}")
        for n in sorted(set(got) - set(expected)):
            errors.append(f"{regime}: unexpected {n}")
        for d in by_regime[regime]:
            if not d.prose.strip():
                errors.append(f"{regime} {d.number}: empty prose")
                continue
            if _ARTIFACTS.search(d.prose):
                errors.append(f"{regime} {d.number}: print artifact in prose")
            if not d.title:
                errors.append(f"{regime} {d.number}: missing title")
            if d.number.isdigit() and len(d.title) > 80:
                errors.append(f"{regime} {d.number}: suspicious title ({len(d.title)} chars)")
            if (d.number.isdigit() and len(d.prose) < 40
                    and not _is_reserved_stub(d)):
                errors.append(f"{regime} {d.number}: prose suspiciously short")
    return errors


def report(docs: list[RuleDoc]) -> None:
    print(f"{'regime':<15}{'rules':>6}{'annexes':>9}{'words':>9}")
    for regime in EXPECTED:
        rs = [d for d in docs if d.regime == regime]
        rules = [d for d in rs if d.number.isdigit()]
        annexes = [d for d in rs if not d.number.isdigit()]
        words = sum(len(d.prose.split()) for d in rs)
        print(f"{regime:<15}{len(rules):>6}{len(annexes):>9}{words:>9}")
    print("\nNote: annex tables (esp. Annex I/III) are reflowed plain text — "
          "include them in the human review sample.")
