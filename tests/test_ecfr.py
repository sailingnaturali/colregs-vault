from pathlib import Path

import pytest

from colregs_build.ecfr import ANNEX_PARTS, parse_annex, parse_rules

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


def test_annex_parts_map():
    assert ANNEX_PARTS == {84: "Annex I", 85: "Annex II", 86: "Annex III",
                           87: "Annex IV", 88: "Annex V"}


@pytest.mark.parametrize("part_no,min_len", [(84, 2000), (86, 500), (87, 200), (88, 500)])
def test_annexes_have_substance(part_no, min_len):
    xml = (SOURCES / f"ecfr-title33-part{part_no}.xml").read_text()
    doc = parse_annex(xml, part_no, "https://example.test", "2026-06-06")
    assert doc.number == ANNEX_PARTS[part_no]
    assert doc.regime == "inland"
    assert doc.part == ""
    assert doc.title
    assert len(doc.prose) > min_len


def test_annex_2_is_reserved_stub():
    xml = (SOURCES / "ecfr-title33-part85.xml").read_text()
    doc = parse_annex(xml, 85, "https://example.test", "2026-06-06")
    assert doc.number == "Annex II"
    assert doc.title == "[Reserved]"
    assert "reserved" in doc.prose.lower()


def test_annex_1_extract_blocks_are_captured():
    xml = (SOURCES / "ecfr-title33-part84.xml").read_text()
    doc = parse_annex(xml, 84, "https://example.test", "2026-06-06")
    # EXTRACT blocks hold the intensity/chromaticity values; without them the
    # prose was ~14,100 chars. With them it must be substantially longer.
    assert len(doc.prose) > 15000


def test_annex_tables_are_extracted():
    # parts 84 and 86 each contain one HTML-style TABLE (TR/TD/TH);
    # rows must surface as "cell | cell" lines in the prose
    for part_no in (84, 86):
        xml = (SOURCES / f"ecfr-title33-part{part_no}.xml").read_text()
        doc = parse_annex(xml, part_no, "https://example.test", "2026-06-06")
        assert " | " in doc.prose, f"part {part_no}: no table rows in prose"
