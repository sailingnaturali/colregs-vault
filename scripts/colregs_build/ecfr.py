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


def _paragraphs(container: ET.Element) -> list[str]:
    out: list[str] = []
    for child in container:
        if child.tag in ("P", "FP", "FP-2", "HD3"):
            t = _text(child)
            if t:
                out.append(t)
        elif child.tag in ("GPOTABLE", "TABLE"):
            rows = []
            for row in child.iter("TR"):
                cells = [_text(c) for c in row if c.tag in ("TD", "TH")]
                line = " | ".join(c for c in cells if c)
                if line:
                    rows.append(line)
            if rows:
                out.append("\n".join(rows))
        elif child.tag in ("EXTRACT", "DIV"):
            out.extend(_paragraphs(child))
        elif child.tag in ("HEAD", "HED", "CITA"):
            # HEAD is the section title (emitted by callers); CITA is citation metadata;
            # HED is the label heading inside NOTE blocks (e.g. "Note:").
            # All are intentionally skipped here.
            pass
        elif child.tag == "img":
            # Formula images (e.g. §84.19 high-speed craft formula) have no text
            # alternative in the eCFR XML. This is an accepted content loss; the
            # omission is flagged in the build report's annex-table note for human review.
            pass
        elif child.tag == "NOTE":
            # NOTE blocks (HED + P) carry regulatory notes; recurse to capture P children.
            out.extend(_paragraphs(child))
        else:
            t = _text(child)
            if t:
                raise ValueError(f"_paragraphs: unexpected tag <{child.tag}> with text content")
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


def parse_annex(xml_text: str, part_no: int, source_url: str, retrieved: str) -> RuleDoc:
    number = ANNEX_PARTS[part_no]
    root = ET.fromstring(xml_text)
    if part_no == 85:
        return RuleDoc(number=number, regime="inland", title="[Reserved]",
                       source_url=source_url, retrieved=retrieved,
                       prose="33 CFR Part 85 (Annex II) is reserved in the "
                             "Inland Navigation Rules.")
    head = _text(root.find("HEAD"))  # e.g. "PART 84—ANNEX I: POSITIONING AND ..."
    title = head.split(":", 1)[1].strip() if ":" in head else head
    paras: list[str] = []
    for div8 in root.iter("DIV8"):
        sec_head = _text(div8.find("HEAD"))
        if sec_head:
            paras.append(sec_head)
        paras.extend(_paragraphs(div8))
    prose = "\n\n".join(paras)
    if not prose:
        raise ValueError(f"empty prose for inland {number}")
    return RuleDoc(number=number, regime="inland", title=title,
                   source_url=source_url, retrieved=retrieved, prose=prose)
