from pathlib import Path

import pytest

from colregs_build.ecfr import parse_rules

SOURCES = Path(__file__).resolve().parent.parent / "sources"


@pytest.fixture(scope="module")
def rules():
    xml = (SOURCES / "ecfr-title33-part83.xml").read_text()
    return parse_rules(xml, "https://example.test/part83", "2026-06-06")


def test_exactly_38_rules(rules):
    assert [r.number for r in rules] == [str(n) for n in range(1, 39)]


def test_metadata_extraction(rules):
    r5 = next(r for r in rules if r.number == "5")
    assert r5.title == "Look-out"
    assert r5.part == "B"
    assert r5.regime == "inland"
    assert r5.source_url == "https://example.test/part83"
    assert r5.retrieved == "2026-06-06"


def test_parts_cover_a_through_e(rules):
    assert {r.part for r in rules} == set("ABCDE")


def test_prose_is_populated_and_clean(rules):
    for r in rules:
        assert len(r.prose) > 40, f"rule {r.number} prose too short"
        assert "§" not in r.prose.split("\n")[0][:5]  # section heads not leaked into prose
    r1 = next(r for r in rules if r.number == "1")
    assert r1.prose.startswith("(a)")
