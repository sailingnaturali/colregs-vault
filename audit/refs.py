"""Resolve a COLREGS citation to its rule file and load that file's prose.

Single source of truth for citation parsing — imported by both the audit harness
and tests/test_data_files.py.
"""
from __future__ import annotations

import re
from pathlib import Path

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def ref_to_file(citation: str) -> str | None:
    """'Annex II 2(a)(ii)' -> 'annex-2.md'; 'Rule 24(a)(i)' -> 'rule-24.md'; else None."""
    annex = re.search(r"Annex\s+([IVX]+)", citation)
    if annex:
        return f"annex-{ROMAN[annex.group(1)]}.md"
    num = re.search(r"(\d+)", citation)
    return f"rule-{int(num.group(1)):02d}.md" if num else None


def load_rule_prose(vault_root: Path, citation: str,
                    regime: str = "international") -> str | None:
    """The cited rule's prose with YAML frontmatter stripped, or None if unresolved."""
    filename = ref_to_file(citation)
    if not filename:
        return None
    path = Path(vault_root) / "rules" / regime / filename
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        _, _frontmatter, body = text.split("---", 2)
        return body.strip()
    return text.strip()
