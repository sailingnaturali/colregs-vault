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
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from colregs_build import ecfr, handbook, justice          # noqa: E402
from colregs_build.fetch import (ECFR_URL, ECFR_PARTS, JUSTICE_URL, ecfr_path,
                                 fetch_sources, justice_path, meta_path)  # noqa: E402
from colregs_build.model import RuleDoc, write_doc          # noqa: E402

EXPECTED: dict[str, list[str]] = {
    "international": [str(n) for n in range(1, 39)]
                     + ["Annex I", "Annex II", "Annex III", "Annex IV"],
    "inland": [str(n) for n in range(1, 39)]
              + ["Annex I", "Annex II", "Annex III", "Annex IV", "Annex V"],
    "canadian": [str(n) for n in range(1, 47)]
                + ["Annex I", "Annex II", "Annex III", "Annex IV"],
}
_ARTIFACTS = re.compile(r"—CONTINUED|\(continued\)", re.IGNORECASE)


def _is_reserved_stub(d: RuleDoc) -> bool:
    return "reserved" in d.prose[:60].lower()


def validate(docs: list[RuleDoc]) -> list[str]:
    errors: list[str] = []
    by_regime: dict[str, list[RuleDoc]] = {r: [] for r in EXPECTED}
    for d in docs:
        by_regime.setdefault(d.regime, []).append(d)
    for regime, expected in EXPECTED.items():
        got = [d.number for d in by_regime[regime]]
        for n in sorted(set(expected) - set(got)):
            errors.append(f"{regime}: missing {n}")
        for n in sorted(set(got) - set(expected)):
            errors.append(f"{regime}: unexpected {n}")
        for d in by_regime[regime]:
            if not d.prose.strip():
                errors.append(f"{regime} {d.number}: empty prose")
                continue
            if _ARTIFACTS.search(d.prose):
                errors.append(f"{regime} {d.number}: print artifact in prose")
            if not d.title:
                errors.append(f"{regime} {d.number}: missing title")
            if d.number.isdigit() and len(d.title) > 80:
                errors.append(f"{regime} {d.number}: suspicious title ({len(d.title)} chars)")
            if (d.number.isdigit() and len(d.prose) < 20
                    and not _is_reserved_stub(d)):
                errors.append(f"{regime} {d.number}: prose suspiciously short")
    return errors


def report(docs: list[RuleDoc]) -> None:
    print(f"{'regime':<15}{'rules':>6}{'annexes':>9}{'words':>9}")
    for regime in EXPECTED:
        rs = [d for d in docs if d.regime == regime]
        rules = [d for d in rs if d.number.isdigit()]
        annexes = [d for d in rs if not d.number.isdigit()]
        words = sum(len(d.prose.split()) for d in rs)
        print(f"{regime:<15}{len(rules):>6}{len(annexes):>9}{words:>9}")
    print("\nNote: annex tables (esp. Annex I/III) are reflowed plain text — "
          "include them in the human review sample.")


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

    pages = handbook.international_pages(
        handbook.split_pages(handbook.run_pdftotext(str(handbook_pdf))))
    docs += handbook.parse_international(pages, handbook_pdf.name)

    errors = validate(docs)
    if errors:
        sys.exit("BUILD FAILED:\n  " + "\n  ".join(errors))

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
