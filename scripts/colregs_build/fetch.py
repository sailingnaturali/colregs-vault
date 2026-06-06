"""Download the eCFR and Justice Laws XML sources into sources/ for reproducible builds."""
from __future__ import annotations

import datetime
from pathlib import Path

import httpx
import yaml

ECFR_URL = "https://www.ecfr.gov/api/versioner/v1/full/{date}/title-33.xml?part={part}"
JUSTICE_URL = "https://laws-lois.justice.gc.ca/eng/XML/C.R.C.,_c._1416.xml"
ECFR_PARTS = (83, 84, 85, 86, 87, 88)


def ecfr_path(sources_dir: Path, part: int) -> Path:
    return sources_dir / f"ecfr-title33-part{part}.xml"


def justice_path(sources_dir: Path) -> Path:
    return sources_dir / "justice-crc-1416.xml"


def meta_path(sources_dir: Path) -> Path:
    return sources_dir / "meta.yaml"


def fetch_sources(sources_dir: Path, ecfr_date: str) -> None:
    sources_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for part in ECFR_PARTS:
            r = client.get(ECFR_URL.format(date=ecfr_date, part=part))
            r.raise_for_status()
            ecfr_path(sources_dir, part).write_bytes(r.content)
        r = client.get(JUSTICE_URL)
        r.raise_for_status()
        justice_path(sources_dir).write_bytes(r.content)
    meta = {"retrieved": datetime.date.today().isoformat(), "ecfr_date": ecfr_date}
    meta_path(sources_dir).write_text(yaml.safe_dump(meta, sort_keys=False))
