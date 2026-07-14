"""Build the colregs vault from authoritative sources. Deterministic; all-or-nothing.

Usage:
    uv run python scripts/build_vault.py --handbook <path-to-USCG-handbook.pdf>
    uv run python scripts/build_vault.py --fetch --ecfr-date 2026-06-01 --handbook <PDF>

Requires poppler's pdftotext on PATH (brew install poppler).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from colregs_build import ecfr, handbook, justice          # noqa: E402
from colregs_build.fetch import (ECFR_URL, ECFR_PARTS, JUSTICE_URL, ecfr_path,
                                 fetch_sources, justice_path, meta_path)  # noqa: E402
from colregs_build.model import RuleDoc, write_doc          # noqa: E402
from colregs_build.validate import EXPECTED, report, validate  # noqa: E402


def write_manifest(root: Path, ecfr_date: str, retrieved: str,
                   handbook_file: Path, justice_amended: str) -> None:
    sha = hashlib.sha256(handbook_file.read_bytes()).hexdigest()
    manifest = {
        "generated_by": "scripts/build_vault.py — do not hand-edit",
        "generated": datetime.date.today().isoformat(),
        "sources": [
            {"title": "USCG Navigation Rules and Regulations Handbook",
             "file": handbook_file.name, "sha256": sha,
             "regimes": ["international"],
             "license": "US Government work — public domain"},
            {"title": "33 CFR Parts 83-88 (Inland Navigation Rules)",
             "url_template": ECFR_URL, "ecfr_date": ecfr_date, "retrieved": retrieved,
             "regimes": ["inland"],
             "license": "US Government work — public domain"},
            {"title": "Collision Regulations, C.R.C., c. 1416 "
                      "(incl. Canadian Modifications)",
             "url": JUSTICE_URL, "last_amended": justice_amended,
             "retrieved": retrieved, "regimes": ["canadian"],
             "license": "Crown copyright — reproducible under the "
                        "Reproduction of Federal Law Order"},
        ],
    }
    (root / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))


def build(vault_root: Path, handbook_pdf: Path, fetch: bool, ecfr_date: str) -> None:
    sources = vault_root / "sources"
    if fetch:
        fetch_sources(sources, ecfr_date)
    meta = yaml.safe_load(meta_path(sources).read_text())
    retrieved, ecfr_date = meta["retrieved"], meta["ecfr_date"]

    docs: list[RuleDoc] = []
    for part in ECFR_PARTS:
        xml_text = ecfr_path(sources, part).read_text()
        url = ECFR_URL.format(date=ecfr_date, part=part)
        if part == 83:
            docs += ecfr.parse_rules(xml_text, url, retrieved)
        else:
            docs.append(ecfr.parse_annex(xml_text, part, url, retrieved))

    justice_xml = justice_path(sources).read_text()
    docs += justice.parse_schedule(justice_xml, retrieved)
    sched = ET.fromstring(justice_xml).find("Schedule")
    justice_amended = sched.get("{http://justice.gc.ca/lims}lastAmendedDate", "")

    raw = handbook.strip_figure_captions(handbook.run_pdftotext(str(handbook_pdf)))
    pages = handbook.international_pages(handbook.split_pages(raw))
    docs += handbook.parse_international(pages, handbook_pdf.name)

    errors = validate(docs)
    if errors:
        sys.exit("BUILD FAILED:\n  " + "\n  ".join(errors))

    # ponytail: write phase isn't atomic — validate() above gates it, but a crash
    # after the unlink loop leaves rules/ half-rewritten. Fine for a one-shot local
    # build tool; make it write-to-temp-then-swap if it ever runs unattended.
    rules_dir = vault_root / "rules"
    old = {p: p.read_text() for p in rules_dir.rglob("*.md")}
    for p in old:
        p.unlink()
    for doc in docs:
        write_doc(doc, rules_dir, old)
    write_manifest(vault_root, ecfr_date, retrieved, handbook_pdf, justice_amended)
    report(docs)
    print(f"\nwrote {len(docs)} files under {rules_dir}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--handbook", required=True, type=Path,
                    help="path to the USCG Nav Rules Handbook PDF")
    ap.add_argument("--fetch", action="store_true",
                    help="re-download XML sources before building")
    ap.add_argument("--ecfr-date", default="2026-06-01")
    ap.add_argument("--vault-root", type=Path,
                    default=Path(__file__).resolve().parent.parent)
    args = ap.parse_args()
    build(args.vault_root, args.handbook, args.fetch, args.ecfr_date)


if __name__ == "__main__":
    main()
