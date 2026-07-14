"""Rank flagged rows and render a markdown audit report.

Rows are split by consensus: a row where >= CONSENSUS_MIN models agree "wrong" is a real
review item; a row only one model dissents on is likely that model's noise, so it is
demoted to a separate section instead of dominating the list.
"""
from __future__ import annotations

CONSENSUS_MIN = 2


def _wrong_votes(verdicts: dict) -> int:
    return sum(1 for v in verdicts.values() if v["verdict"] == "wrong")


def _flagged(verdicts: dict) -> bool:
    kinds = [v["verdict"] for v in verdicts.values()]
    return any(k == "wrong" for k in kinds) or len(set(kinds)) > 1


def _rank_key(verdicts: dict):
    kinds = [v["verdict"] for v in verdicts.values()]
    return (-sum(1 for k in kinds if k == "wrong"), -len(set(kinds)))


def _render_row(lines: list[str], item, verdicts: dict, model_names: list[str]) -> None:
    lines.append(f"### {item.source} · {item.row_id} → `{item.citation}` "
                 f"({_wrong_votes(verdicts)}/{len(model_names)} wrong)")
    lines.append(f"_{item.situation} · {item.signal_desc}_")
    for name in model_names:
        v = verdicts[name]
        fix = f" — suggest `{v['suggested_fix']}`" if v["suggested_fix"] else ""
        lines.append(f"- **{name}**: {v['verdict']} ({v['confidence']:.2f}) — {v['reason']}{fix}")
    lines.append("")


def render(results, model_names: list[str], date: str) -> str:
    flagged = [(item, v) for item, v in results if _flagged(v)]
    consensus = sorted([iv for iv in flagged if _wrong_votes(iv[1]) >= CONSENSUS_MIN],
                       key=lambda iv: _rank_key(iv[1]))
    single = sorted([iv for iv in flagged if _wrong_votes(iv[1]) < CONSENSUS_MIN],
                    key=lambda iv: _rank_key(iv[1]))

    lines = [f"# colregs-vault audit — {date}", "",
             f"Models: {', '.join(model_names)}", "",
             f"{len(consensus)} consensus concern(s) (≥{CONSENSUS_MIN} models agree wrong) · "
             f"{len(single)} single-model flag(s) · {len(results)} rows checked.", ""]

    lines.append(f"## Consensus concerns (≥{CONSENSUS_MIN} models wrong)")
    if consensus:
        for item, verdicts in consensus:
            _render_row(lines, item, verdicts, model_names)
    else:
        lines.append("_None — no row was flagged wrong by "
                     f"{CONSENSUS_MIN} or more models._")
        lines.append("")

    lines.append("## Single-model flags (one model dissents — likely noise)")
    if single:
        for item, verdicts in single:
            _render_row(lines, item, verdicts, model_names)
    else:
        lines.append("_None._")
        lines.append("")

    lines.append("## Model agreement")
    for name in model_names:
        counts = {"ok": 0, "wrong": 0, "unsure": 0}
        for _item, verdicts in results:
            counts[verdicts[name]["verdict"]] += 1
        lines.append(f"- {name}: ok {counts['ok']}, "
                     f"wrong {counts['wrong']}, unsure {counts['unsure']}")
    return "\n".join(lines) + "\n"
