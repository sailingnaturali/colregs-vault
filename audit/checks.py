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
    signal_desc: str
    citation: str
    rule_prose: str | None


def _requirements_rows(data):
    """Yield (row_id, situation, signal_desc, ref) from requirements.yaml."""
    for entry in data.get("entries", []):
        rid = entry["id"]
        situation = entry.get("match", {}).get("situation", "")
        lights = list(entry.get("lights", [])) + list(entry.get("shapes", []))
        for opt in entry.get("light_options", []):
            lights += list(opt)
        for light in lights:
            if "rule" in light:
                yield rid, situation, light.get("desc", ""), light["rule"]


def _sightings_rows(data):
    """Yield (row_id, situation, signal_desc, ref) from sightings.yaml."""
    for pat in data.get("patterns", []):
        rid = pat["id"]
        arrangement = "+".join(pat.get("arrangement", []))
        condition = pat.get("condition", "")
        for cand in pat.get("candidates", []):
            note = cand.get("note", "")
            desc = f"{arrangement} [{condition}]: {note}".strip()
            yield rid, cand.get("situation", ""), desc, cand["rule"]


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
        for rid, situation, signal, ref in extractor(data):
            for citation in (s.strip() for s in ref.split("+")):
                key = (name, rid, citation)
                if key in seen:
                    continue
                seen.add(key)
                items.append(CheckItem(
                    source=name, row_id=rid, situation=situation,
                    signal_desc=signal, citation=citation,
                    rule_prose=load_rule_prose(vault_root, citation)))
    return items
