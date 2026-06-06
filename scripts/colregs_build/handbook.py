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
