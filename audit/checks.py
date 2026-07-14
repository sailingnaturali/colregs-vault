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
    signal_desc: str     # the specific light/shape this citation is attached to
    citation: str
    rule_prose: str | None
    condition: str = ""       # "day" | "night"
    length: str = ""          # "under 50 m" | "50 m or more"
    full_signal: str = ""     # the row's complete arrangement, so the citation is judged in context


def _length_phrase(match: dict) -> str:
    if "length_lt" in match:
        return f"under {match['length_lt']} m"
    if "length_gte" in match:
        return f"{match['length_gte']} m or more"
    return ""


def _requirements_rows(data):
    """Yield (row_id, situation, signal_desc, ref, condition, length, full_signal)."""
    for entry in data.get("entries", []):
        rid = entry["id"]
        match = entry.get("match", {})
        situation = match.get("situation", "")
        condition = match.get("condition", "")
        length = _length_phrase(match)
        lights = list(entry.get("lights", [])) + list(entry.get("shapes", []))
        # full_signal shows the fixed lights/shapes plus any light_options as *alternatives*
        # (they are either/or, so flattening them into one list would read as contradictory).
        parts = []
        fixed = [l["desc"] for l in lights if l.get("desc")]
        if fixed:
            parts.append("; ".join(fixed))
        option_sets = []
        for opt in entry.get("light_options", []):
            lights += list(opt)
            descs = [l["desc"] for l in opt if l.get("desc")]
            if descs:
                option_sets.append(", ".join(descs))
        if option_sets:
            parts.append("one of: " + " OR ".join(f"[{s}]" for s in option_sets))
        full_signal = "; ".join(parts)
        for light in lights:
            if "rule" in light:
                yield (rid, situation, light.get("desc", ""), light["rule"],
                       condition, length, full_signal)


def _sightings_rows(data):
    """Yield (row_id, situation, signal_desc, ref, condition, length, full_signal)."""
    for pat in data.get("patterns", []):
        rid = pat["id"]
        arrangement = ", ".join(pat.get("arrangement", []))
        condition = pat.get("condition", "")
        for cand in pat.get("candidates", []):
            note = cand.get("note", "")
            desc = f"{arrangement} [{condition}]: {note}".strip()
            yield (rid, cand.get("situation", ""), desc, cand["rule"],
                   condition, "", arrangement)


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
        for rid, situation, signal, ref, condition, length, full_signal in extractor(data):
            for citation in (s.strip() for s in ref.split("+")):
                key = (name, rid, citation)
                if key in seen:
                    continue
                seen.add(key)
                items.append(CheckItem(
                    source=name, row_id=rid, situation=situation,
                    signal_desc=signal, citation=citation,
                    rule_prose=load_rule_prose(vault_root, citation),
                    condition=condition, length=length, full_signal=full_signal))
    return items
