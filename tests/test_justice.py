from pathlib import Path

import pytest

from colregs_build.justice import parse_schedule

SOURCES = Path(__file__).resolve().parent.parent / "sources"


@pytest.fixture(scope="module")
def docs():
    xml = (SOURCES / "justice-crc-1416.xml").read_text()
    return parse_schedule(xml, "2026-06-06")


def test_rules_1_through_46_plus_annexes(docs):
    numbers = [d.number for d in docs]
    assert [n for n in numbers if n.isdigit()] == [str(n) for n in range(1, 47)]
    assert [n for n in numbers if n.startswith("Annex")] == [
        "Annex I", "Annex II", "Annex III", "Annex IV"]


def test_parts_a_through_f(docs):
    by_num = {d.number: d for d in docs}
    assert by_num["1"].part == "A"
    assert by_num["5"].part == "B"
    assert by_num["39"].part == "F"
    assert by_num["46"].part == "F"


def test_titles_strip_international_suffix(docs):
    by_num = {d.number: d for d in docs}
    assert by_num["1"].title == "Application"
    assert by_num["5"].title == "Look-out"
    assert by_num["39"].title == "Special Signals for Dangerous Goods"


def test_canadian_modifications_present_in_prose(docs):
    by_num = {d.number: d for d in docs}
    assert "Canadian Modification" in by_num["1"].prose
    assert "Canadian Modifications" in by_num["6"].prose


def test_provision_labels_are_space_separated(docs):
    r1 = next(d for d in docs if d.number == "1")
    assert r1.prose.splitlines()[1].startswith("(a) ")  # line 0 is the "— International" heading


def test_all_docs_have_prose(docs):
    for d in docs:
        assert d.prose.strip(), f"{d.number} empty"
        assert d.regime == "canadian"


def test_annex_titles_strip_international_suffix(docs):
    by_num = {d.number: d for d in docs}
    assert not by_num["Annex IV"].title.upper().endswith("INTERNATIONAL")
    assert not by_num["Annex II"].title.upper().endswith("INTERNATIONAL")
    assert by_num["Annex IV"].title  # still non-empty
