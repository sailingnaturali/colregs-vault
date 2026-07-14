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
