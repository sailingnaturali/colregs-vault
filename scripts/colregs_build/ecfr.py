"""Parse eCFR title 33 XML: part 83 -> inland rules, parts 84-88 -> inland annexes."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .model import RuleDoc

ANNEX_PARTS = {84: "Annex I", 85: "Annex II", 86: "Annex III", 87: "Annex IV", 88: "Annex V"}
_HEAD_RE = re.compile(r"§\s*83\.\d+\s+(.*?)\s*\(Rule\s+(\d+)\)\.?\s*$")


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _paragraphs(div8: ET.Element) -> list[str]:
    out: list[str] = []
    for child in div8:
        if child.tag == "P":
            t = _text(child)
            if t:
                out.append(t)
        elif child.tag in ("GPOTABLE", "TABLE"):
            rows = []
            for row in child.iter("ROW"):
                cells = [_text(c) for c in row.iter("ENT")]
                rows.append(" | ".join(c for c in cells if c))
            if rows:
                out.append("\n".join(rows))
        elif child.tag == "HD3":
            t = _text(child)
            if t:
                out.append(t)
        elif child.tag == "FP-2":
            t = _text(child)
            if t:
                out.append(t)
        # CITA (citation metadata) and HEAD are intentionally skipped
    return out


def parse_rules(xml_text: str, source_url: str, retrieved: str) -> list[RuleDoc]:
    root = ET.fromstring(xml_text)
    docs: list[RuleDoc] = []
    for div6 in root.iter("DIV6"):
        part = div6.get("N", "")
        for div8 in div6.iter("DIV8"):
            head = _text(div8.find("HEAD"))
            m = _HEAD_RE.search(head)
            if not m:
                raise ValueError(f"unrecognized eCFR section head: {head!r}")
            title, rule_no = m.group(1), m.group(2)
            prose = "\n\n".join(_paragraphs(div8))
            if not prose:
                # [Reserved] sections have no paragraph children; use the section
                # heading text as a minimal prose marker so downstream consumers
                # get a non-empty string and the rule is still included.
                if "[Reserved]" in head:
                    prose = f"[Reserved] — Rule {rule_no} is reserved and contains no operative text."
                else:
                    raise ValueError(f"empty prose for inland Rule {rule_no}")
            docs.append(RuleDoc(number=rule_no, regime="inland", part=part, title=title,
                                source_url=source_url, retrieved=retrieved, prose=prose))
    docs.sort(key=lambda d: int(d.number))
    return docs
