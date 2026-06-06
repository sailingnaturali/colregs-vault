"""Parse the Canadian Collision Regulations (C.R.C., c. 1416) Justice Laws XML.

Schedule 1 is a flat stream of Heading/Provision elements; headings carry the
Part / Rule N / subtitle / ANNEX structure, including '— Canadian Modification(s)'
markers, which are preserved verbatim as prose lines.
"""
from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET

from .model import RuleDoc

SOURCE_URL = "https://laws-lois.justice.gc.ca/eng/XML/C.R.C.,_c._1416.xml"
_PART_RE = re.compile(r"^PART ([A-F])\b")
_RULE_RE = re.compile(r"^Rule (\d+)$")
_ANNEX_RE = re.compile(r"^ANNEX ([IV]+)")
_SECTION_RE = re.compile(r"^SECTION [IVX]+\b")
_INTL_SUFFIX = re.compile(r"\s*—\s*International$")
# Non-substantive elements excluded from prose AND from the fidelity baseline:
_NOTES = {"HistoricalNote", "MarginalNote", "FootnoteRef", "Footnote"}


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _flat_without_notes(el: ET.Element) -> str:
    c = copy.deepcopy(el)
    for parent in c.iter():
        for child in list(parent):
            if child.tag in _NOTES:
                parent.remove(child)
    return _squash("".join(c.itertext()))


def _table_text(table_group: ET.Element) -> str:
    """Render a CALS TableGroup (table/tgroup/thead|tbody/row/entry) as pipe-joined rows.
    Uses _flat_without_notes on each entry to strip FootnoteRef markers so the fidelity
    baseline (which also strips Footnotes/FootnoteRefs) matches."""
    rows: list[str] = []
    for section in table_group.iter("table"):
        for tgroup in section.iter("tgroup"):
            for thead in tgroup.findall("thead"):
                for row in thead.findall("row"):
                    cells = [_flat_without_notes(e) for e in row.findall("entry")]
                    line = " | ".join(c for c in cells if c)
                    if line:
                        rows.append(line)
            for tbody in tgroup.findall("tbody"):
                for row in tbody.findall("row"):
                    cells = [_flat_without_notes(e) for e in row.findall("entry")]
                    line = " | ".join(c for c in cells if c)
                    if line:
                        rows.append(line)
    return "\n".join(rows)


def _formula_text(fg: ET.Element) -> str:
    """Render a FormulaGroup: formula text + where-definitions."""
    parts: list[str] = []
    for child in fg:
        if child.tag == "Formula":
            formula_text = _squash("".join(child.itertext()))
            if formula_text:
                parts.append(formula_text)
        elif child.tag == "FormulaConnector":
            t = _squash("".join(child.itertext()))
            if t:
                parts.append(t)
        elif child.tag == "FormulaDefinition":
            t = _squash("".join(child.itertext()))
            if t:
                parts.append(t)
        elif child.tag in _NOTES:
            pass
        else:
            t = _squash("".join(child.itertext()))
            if t:
                parts.append(t)
    return "\n".join(parts)


def _provision_text(prov: ET.Element) -> str:
    """Flatten a Provision: each labelled sub-element becomes its own line,
    with a space between Label ('(a)') and Text. Handles nested Headings,
    TableGroups, FormulaGroups, and Repealed elements recursively."""
    lines: list[str] = []

    def emit(el: ET.Element) -> None:
        label = el.find("Label")
        text_el = el.find("Text")
        chunk = ""
        if label is not None:
            chunk = _squash("".join(label.itertext()))
        if text_el is not None:
            chunk = (chunk + " " + _flat_without_notes(text_el)).strip()
        if chunk:
            lines.append(chunk)
        for child in el:
            if child.tag in ("Label", "Text") or child.tag in _NOTES:
                continue
            if child.tag == "Provision":
                emit(child)
            elif child.tag == "Heading":
                # Inline heading (Canadian Modification sub-header inside a Provision)
                title_text = child.find("TitleText")
                if title_text is not None:
                    t = _squash("".join(title_text.itertext()))
                else:
                    t = _squash("".join(child.itertext()))
                if t:
                    lines.append(t)
            elif child.tag == "TableGroup":
                t = _table_text(child)
                if t:
                    lines.append(t)
            elif child.tag == "FormulaGroup":
                t = _formula_text(child)
                if t:
                    lines.append(t)
            elif child.tag == "Repealed":
                t = _squash("".join(child.itertext()))
                if t:
                    lines.append(t)
            else:
                # Unknown child — fall through to fidelity check
                pass

    emit(prov)
    if not lines:
        t = _flat_without_notes(prov)
        if t:
            lines.append(t)
    # Fidelity invariant: flattening must not lose any word characters.
    joined = re.sub(r"\W", "", "".join(lines))
    flat = re.sub(r"\W", "", _flat_without_notes(prov))
    if joined != flat:
        raise ValueError(f"text lost flattening provision (lens {len(joined)} vs {len(flat)})")
    return "\n".join(lines)


def parse_schedule(xml_text: str, retrieved: str) -> list[RuleDoc]:
    root = ET.fromstring(xml_text)
    sched = root.find("Schedule")  # Schedule 1 = the rules; later schedules are repealed
    if sched is None:
        raise ValueError("no Schedule element found")
    docs: list[RuleDoc] = []
    part = ""
    current: RuleDoc | None = None
    pending_title = False

    def push() -> None:
        nonlocal current
        if current is not None:
            if not current.prose.strip():
                raise ValueError(f"canadian {current.number}: no prose collected")
            docs.append(current)
            current = None

    for el in sched:
        if el.tag == "Heading":
            text = _squash("".join(el.itertext()))
            pm = _PART_RE.match(text)
            if pm:
                part = pm.group(1)
                continue
            if _SECTION_RE.match(text):
                continue
            rm = _RULE_RE.match(text)
            if rm:
                push()
                current = RuleDoc(number=rm.group(1), regime="canadian", part=part,
                                  source_url=SOURCE_URL, retrieved=retrieved)
                pending_title = True
                continue
            am = _ANNEX_RE.match(text)
            if am:
                push()
                title = _INTL_SUFFIX.sub("", text[len(am.group(0)):].strip(" —-"))
                current = RuleDoc(number=f"Annex {am.group(1)}", regime="canadian",
                                  title=title, source_url=SOURCE_URL, retrieved=retrieved)
                pending_title = False
                continue
            if current is None:
                continue  # schedule front-matter headings before PART A
            if pending_title:
                current.title = _INTL_SUFFIX.sub("", text)
                pending_title = False
                if "—" not in text:
                    continue  # plain title; only keep structural headings in prose
            current.prose += ("\n" if current.prose else "") + text
        elif el.tag == "Provision":
            if current is not None:
                current.prose += ("\n" if current.prose else "") + _provision_text(el)
        elif el.tag in ("ScheduleFormHeading", "HistoricalNote"):
            continue
        else:
            stray = _squash("".join(el.itertext()))
            if stray:
                raise ValueError(f"unhandled schedule element <{el.tag}>: tag only — probe structure")
    push()
    return docs
