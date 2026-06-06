"""RuleDoc record and markdown writer for the vault build."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


@dataclass
class RuleDoc:
    number: str                       # "5", "39", or "Annex I"
    regime: str                       # international | inland | canadian
    part: str = ""                    # A-F for rules; "" for annexes
    title: str = ""
    source_pdf: str | None = None     # international regime
    source_url: str | None = None     # inland / canadian regimes
    retrieved: str | None = None      # YYYY-MM-DD (date the source was fetched)
    prose: str = ""

    def filename(self) -> str:
        if self.number.startswith("Annex"):
            return f"annex-{_ROMAN[self.number.split()[1]]}.md"
        return f"rule-{int(self.number):02d}.md"

    def to_markdown(self, verified: bool = False) -> str:
        fm: dict = {"number": self.number, "regime": self.regime}
        if self.part:
            fm["part"] = self.part
        fm["title"] = self.title
        fm["verified"] = verified
        if self.source_pdf:
            fm["source_pdf"] = self.source_pdf
        if self.source_url:
            fm["source_url"] = self.source_url
        if self.retrieved:
            fm["retrieved"] = self.retrieved
        body = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
        return f"---\n{body}\n---\n{self.prose.rstrip()}\n"


def write_doc(doc: RuleDoc, rules_dir: Path, old: dict[Path, str]) -> Path:
    """Write doc under rules/<regime>/. `old` maps pre-build paths to their previous
    content; `verified: true` survives only if the previous prose is identical."""
    out = rules_dir / doc.regime / doc.filename()
    verified = False
    prev = old.get(out)
    if prev is not None and prev.startswith("---"):
        _, fm, prev_prose = prev.split("---", 2)
        meta = yaml.safe_load(fm) or {}
        if meta.get("verified") is True and prev_prose.strip() == doc.prose.strip():
            verified = True
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc.to_markdown(verified=verified), encoding="utf-8")
    return out
