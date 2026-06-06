"""Extract the International (COLREGS 72) rules from the USCG handbook's text layer.

Facing-page layout: every content page opens with an em-dash regime marker
(—INTERNATIONAL— / —INLAND—). We keep only international pages, strip running
headers / page footers / print-continuation artifacts, and split on rule and
annex headings.
"""
from __future__ import annotations

import re
import subprocess

from .model import RuleDoc

RUNNING_HEADERS = {
    "General", "Steering and Sailing Rules", "Lights and Shapes",
    "Sound and Light Signals", "Exemptions",
}
_RULE_START = re.compile(r"^Rule (\d+)$")
_RULE_CONT = re.compile(r"^Rule (\d+)—CONTINUED$")
_ANNEX_START = re.compile(r"^Annex ([IV]+)$")
_ANNEX_CONT = re.compile(r"^Annex ([IV]+)—CONTINUED$")
_PART = re.compile(r"^PART ([A-E])—(.+)$")
_SECTION = re.compile(r"^Section [IVX]+", re.IGNORECASE)
_PARA_CONT = re.compile(r"^\([a-z0-9]+\)\s*\(continued\)$", re.IGNORECASE)
_PARA_START = re.compile(r"^(\([a-z0-9ivx]+\)|\d+\.)\s")
_STOP = "INTERPRETATIVE RULES"


def run_pdftotext(pdf_path: str) -> str:
    return subprocess.run(["pdftotext", pdf_path, "-"],
                          capture_output=True, text=True, check=True).stdout


def split_pages(text: str) -> list[list[str]]:
    pages = []
    for raw in text.split("\f"):
        pages.append([l.strip() for l in raw.splitlines() if l.strip()])
    return pages


def international_pages(pages: list[list[str]]) -> list[tuple[int, list[str]]]:
    """(1-based page index within `pages`, cleaned lines) for international pages."""
    result = []
    for i, lines in enumerate(pages):
        if not lines or lines[0] != "—INTERNATIONAL—":
            continue
        body = lines[1:]
        if body and body[0] in RUNNING_HEADERS:
            body = body[1:]
        body = [l for l in body if l != "[BLANK]"]
        if body and body[-1].isdigit():
            body = body[:-1]
        if body:
            result.append((i + 1, body))
    return result


def _reflow(lines: list[str]) -> str:
    """Rejoin hard-wrapped lines into paragraphs; a new paragraph starts at
    (a)/(i)/1.-style labels."""
    paras: list[str] = []
    for line in lines:
        if _PARA_START.match(line) or not paras:
            paras.append(line)
        else:
            paras[-1] += " " + line
    return "\n\n".join(paras)


def parse_international(pages: list[tuple[int, list[str]]],
                        source_name: str) -> list[RuleDoc]:
    bodies: dict[str, list[str]] = {}      # doc key -> raw content lines
    titles: dict[str, str] = {}
    parts: dict[str, str] = {}
    pagenos: dict[str, set[int]] = {}
    order: list[str] = []
    part = ""
    key: str | None = None
    title_pending = 0                       # 1: next line is the title; -1: multi-line annex title

    def start(k: str, pageno: int, pending: int) -> None:
        nonlocal key, title_pending
        key = k
        title_pending = pending
        if k not in bodies:
            bodies[k] = []
            titles[k] = ""
            parts[k] = part
            pagenos[k] = set()
            order.append(k)
        pagenos[k].add(pageno)

    done = False
    skip_continuation = False
    for pageno, lines in pages:
        if done:
            break
        for line in lines:
            if line == _STOP:
                done = True
                break
            pm = _PART.match(line)
            if pm:
                skip_continuation = False
                part = pm.group(1)
                title_pending = 0  # defensive: headings always precede rules, but don't trust print layout
                continue
            if _SECTION.match(line):
                skip_continuation = True
                title_pending = 0  # defensive: headings always precede rules, but don't trust print layout
                continue
            if _PARA_CONT.match(line):
                continue
            m = _RULE_START.match(line)
            if m:
                skip_continuation = False
                start(m.group(1), pageno, pending=1)   # rule titles are one line
                continue
            m = _RULE_CONT.match(line)
            if m:
                skip_continuation = False
                start(m.group(1), pageno, pending=0)
                continue
            m = _ANNEX_START.match(line)
            if m:
                skip_continuation = False
                start(f"Annex {m.group(1)}", pageno, pending=-1)  # multi-line title
                continue
            m = _ANNEX_CONT.match(line)
            if m:
                skip_continuation = False
                start(f"Annex {m.group(1)}", pageno, pending=0)
                continue
            if skip_continuation:
                continue                     # drop wrapped section-heading continuation lines
            if key is None:
                continue                     # front matter before Rule 1
            if title_pending == 1:
                titles[key] = line
                title_pending = 0
                continue
            if title_pending == -1:          # annex title: accumulate until prose starts
                if _PARA_START.match(line):
                    title_pending = 0        # fall through to prose
                else:
                    titles[key] = (titles[key] + " " + line).strip()
                    continue
            bodies[key].append(line)

    docs: list[RuleDoc] = []
    for k in order:
        nums = sorted(pagenos[k])
        span = f"p. {nums[0]}" if len(nums) == 1 else f"pp. {nums[0]}-{nums[-1]}"
        docs.append(RuleDoc(number=k, regime="international", part=parts[k],
                            title=titles[k], source_pdf=f"{source_name} {span}",
                            prose=_reflow(bodies[k])))
    return docs
