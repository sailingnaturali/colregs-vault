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
        fixed = list(entry.get("lights", [])) + list(entry.get("shapes", []))
        options = [list(o) for o in entry.get("light_options", [])]
        # full_signal shows the fixed lights/shapes plus any light_options as *alternatives*
        # (they are either/or, so flattening them into one list would read as contradictory).
        parts = []
        fixed_descs = [l["desc"] for l in fixed if l.get("desc")]
        if fixed_descs:
            parts.append("; ".join(fixed_descs))
        option_sets = [", ".join(l["desc"] for l in o if l.get("desc")) for o in options]
        option_sets = [s for s in option_sets if s]
        if option_sets:
            parts.append("one of: " + " OR ".join(f"[{s}]" for s in option_sets))
        full_signal = "; ".join(parts)
        # Tag each element with its arrangement group (fixed lights vs each either/or
        # option) so build_checks only combines descriptions actually shown together.
        groups = [("fixed", fixed)] + [(f"option{k}", o) for k, o in enumerate(options)]
        for gname, elements in groups:
            for light in elements:
                if "rule" in light:
                    yield (rid, situation, light.get("desc", ""), light["rule"],
                           condition, length, full_signal, gname)


def _sightings_rows(data):
    """Yield (row_id, situation, signal_desc, ref, condition, length, full_signal)."""
    for pat in data.get("patterns", []):
        rid = pat["id"]
        arrangement = ", ".join(pat.get("arrangement", []))
        condition = pat.get("condition", "")
        for k, cand in enumerate(pat.get("candidates", [])):
            note = cand.get("note", "")
            desc = f"{arrangement} [{condition}]: {note}".strip()
            yield (rid, cand.get("situation", ""), desc, cand["rule"],
                   condition, "", arrangement, f"cand{k}")


def build_checks(vault_root) -> list[CheckItem]:
    vault_root = Path(vault_root)
    sources = [
        ("requirements.yaml", _requirements_rows),
        ("sightings.yaml", _sightings_rows),
    ]
    # Group by (source, row_id, citation): several elements can share one citation —
    # e.g. the two cones of a fishing dayshape, the three balls of a vessel aground.
    # Combine their descriptions so the citation is judged against the whole shape it
    # prescribes — but only within one arrangement group, so either/or light_options
    # (e.g. the 2-light vs 3-light tow, both citing 24(a)(i)) aren't merged into one
    # contradictory signal.
    order: list[tuple[str, str, str]] = []
    grouped: dict[tuple[str, str, str], CheckItem] = {}
    group_of: dict[tuple[str, str, str], str] = {}
    for name, extractor in sources:
        data = yaml.safe_load((vault_root / name).read_text())
        for rid, situation, signal, ref, condition, length, full_signal, arr_group in extractor(data):
            for citation in (s.strip() for s in ref.split("+")):
                key = (name, rid, citation)
                if key not in grouped:
                    order.append(key)
                    group_of[key] = arr_group
                    grouped[key] = CheckItem(
                        source=name, row_id=rid, situation=situation,
                        signal_desc=signal, citation=citation,
                        rule_prose=load_rule_prose(vault_root, citation),
                        condition=condition, length=length, full_signal=full_signal)
                elif (arr_group == group_of[key] and signal
                      and signal not in grouped[key].signal_desc.split("; ")):
                    grouped[key].signal_desc = f"{grouped[key].signal_desc}; {signal}".strip("; ")
    return [grouped[k] for k in order]
