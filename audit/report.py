"""Rank flagged rows and render a markdown audit report.

Flagged rows are bucketed by strength of concern, most-actionable first:
  1. Escalation-confirmed — the strong tier's tiebreak agrees the row is wrong.
  2. Consensus concerns — >= CONSENSUS_MIN jurors agree wrong (a robust, explainable
     split; kept count-based).
  3. Single-model flags — one juror dissents.
Within each, rows are ordered by **weighted risk** = sum over wrong-voters of
`weight x self-confidence`, so an unreliable juror's lone flag ranks below a trusted one.
A fourth section surfaces **blind spots** — unanimous "ok" rows the jury was *least sure*
of, for spot-checking calls that could be a shared bias rather than a real agreement.
"""
from __future__ import annotations

CONSENSUS_MIN = 2
# Weighted-wrong needed to count as a jury "wrong" call (regression gate). ~two mid-weight
# jurors or one perfect one — the weighted analogue of CONSENSUS_MIN.
WEIGHTED_THRESHOLD = 1.0


def _key(item):
    return (item.source, item.row_id, item.citation)


def _wrong_votes(verdicts: dict) -> int:
    return sum(1 for v in verdicts.values() if v["verdict"] == "wrong")


def _flagged(verdicts: dict) -> bool:
    kinds = [v["verdict"] for v in verdicts.values()]
    return any(k == "wrong" for k in kinds) or len(set(kinds)) > 1


def _weighted_risk(verdicts: dict, weights: dict) -> float:
    return sum(weights.get(m, 1.0) * v["confidence"]
               for m, v in verdicts.items() if v["verdict"] == "wrong")


def _mean_confidence(verdicts: dict, weights: dict) -> float:
    total_w = sum(weights.get(m, 1.0) for m in verdicts) or 1.0
    return sum(weights.get(m, 1.0) * v["confidence"]
               for m, v in verdicts.items()) / total_w


def _escalation_says_wrong(esc: dict | None) -> bool:
    return bool(esc) and any(v["verdict"] == "wrong" for v in esc.values())


def _render_row(lines, item, verdicts, model_names, weights, esc=None) -> None:
    risk = _weighted_risk(verdicts, weights)
    lines.append(f"### {item.source} · {item.row_id} → `{item.citation}` "
                 f"({_wrong_votes(verdicts)}/{len(model_names)} wrong · risk {risk:.2f})")
    lines.append(f"_{item.situation} · {item.signal_desc}_")
    for name in model_names:
        v = verdicts[name]
        fix = f" — suggest `{v['suggested_fix']}`" if v["suggested_fix"] else ""
        lines.append(f"- **{name}** (w={weights.get(name, 1.0):.2f}): "
                     f"{v['verdict']} ({v['confidence']:.2f}) — {v['reason']}{fix}")
    if esc:
        for name, v in esc.items():
            fix = f" — suggest `{v['suggested_fix']}`" if v["suggested_fix"] else ""
            lines.append(f"- **escalation → {name}**: {v['verdict']} "
                         f"({v['confidence']:.2f}) — {v['reason']}{fix}")
    lines.append("")


def _section(lines, title, rows, model_names, weights, escalations, empty_msg) -> None:
    lines.append(title)
    if rows:
        for item, verdicts in rows:
            _render_row(lines, item, verdicts, model_names, weights,
                        escalations.get(_key(item)))
    else:
        lines.append(empty_msg)
        lines.append("")


def render(results, model_names: list[str], date: str,
           weights: dict | None = None, escalations: dict | None = None) -> str:
    weights = weights or {}
    escalations = escalations or {}

    def risk(iv):
        return -_weighted_risk(iv[1], weights)

    flagged = [(item, v) for item, v in results if _flagged(v)]
    confirmed, consensus, single = [], [], []
    for item, v in flagged:
        if _escalation_says_wrong(escalations.get(_key(item))):
            confirmed.append((item, v))
        elif _wrong_votes(v) >= CONSENSUS_MIN:
            consensus.append((item, v))
        else:
            single.append((item, v))
    confirmed.sort(key=risk)
    consensus.sort(key=risk)
    single.sort(key=risk)

    # Blind spots: unanimous "ok", ranked by how *unsure* the jury was (weighted mean conf).
    unanimous_ok = [(item, v) for item, v in results
                    if {x["verdict"] for x in v.values()} == {"ok"}]
    blind = sorted(unanimous_ok, key=lambda iv: _mean_confidence(iv[1], weights))[:10]

    lines = [f"# colregs-vault audit — {date}", "",
             f"Models: {', '.join(model_names)}"
             + (f" · escalators: {', '.join(sorted({n for e in escalations.values() for n in e}))}"
                if escalations else ""), "",
             f"{len(confirmed)} escalation-confirmed · {len(consensus)} consensus "
             f"(≥{CONSENSUS_MIN} wrong) · {len(single)} single-model · "
             f"{len(blind)} blind-spot spot-check(s) · {len(results)} rows checked.", ""]

    _section(lines, "## Escalation-confirmed concerns (strong tier agrees wrong)",
             confirmed, model_names, weights, escalations,
             "_None — no flagged row was confirmed wrong by the strong tier "
             "(or no escalator was available)._")
    _section(lines, f"## Consensus concerns (≥{CONSENSUS_MIN} jurors wrong)",
             consensus, model_names, weights, escalations,
             f"_None — no row was flagged wrong by {CONSENSUS_MIN} or more jurors._")
    _section(lines, "## Single-model flags (one juror dissents — likely noise)",
             single, model_names, weights, escalations, "_None._")

    lines.append("## Blind spots (unanimous ok, jury least sure — spot-check these)")
    if blind:
        for item, verdicts in blind:
            lines.append(f"- {item.source} · {item.row_id} → `{item.citation}` "
                         f"(mean conf {_mean_confidence(verdicts, weights):.2f}) — "
                         f"{item.situation} · {item.signal_desc}")
        lines.append("")
    else:
        lines.append("_None._")
        lines.append("")

    lines.append("## Model agreement")
    for name in model_names:
        counts = {"ok": 0, "wrong": 0, "unsure": 0}
        for _item, verdicts in results:
            counts[verdicts[name]["verdict"]] += 1
        lines.append(f"- {name} (weight {weights.get(name, 1.0):.2f}): "
                     f"ok {counts['ok']}, wrong {counts['wrong']}, unsure {counts['unsure']}")
    return "\n".join(lines) + "\n"
