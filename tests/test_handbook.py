from pathlib import Path

from colregs_build.handbook import international_pages, split_pages

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return split_pages((FIXTURES / name).read_text())


def test_split_pages_returns_nonempty_line_lists():
    pages = load("handbook-rules-sample.txt")
    assert len(pages) >= 14
    assert all(isinstance(p, list) for p in pages)


def test_international_pages_filters_and_cleans():
    pages = international_pages(load("handbook-rules-sample.txt"))
    assert pages, "no international pages found"
    for pageno, lines in pages:
        assert "—INTERNATIONAL—" not in lines
        assert "—INLAND—" not in lines
        assert "[BLANK]" not in lines
        assert not (lines and lines[-1].isdigit())     # printed page footer removed
        assert lines and lines[0] not in {"General", "Steering and Sailing Rules"}


def test_page_numbers_are_relative_indices():
    pages = international_pages(load("handbook-rules-sample.txt"))
    assert pages[0][0] >= 1


from colregs_build.handbook import parse_international


def docs_from(name):
    return parse_international(international_pages(load(name)), "handbook.pdf")


def test_rules_sample_yields_contiguous_rules():
    docs = docs_from("handbook-rules-sample.txt")
    numbers = [int(d.number) for d in docs if d.number.isdigit()]
    assert numbers == list(range(min(numbers), max(numbers) + 1))
    assert 1 in numbers and 5 in numbers


def test_rule_metadata():
    docs = docs_from("handbook-rules-sample.txt")
    by = {d.number: d for d in docs}
    assert by["1"].title == "Application"
    assert by["1"].part == "A"
    assert by["5"].part == "B"
    assert by["1"].prose.startswith("(a)")
    assert by["1"].source_pdf.startswith("handbook.pdf p")
    for d in docs:
        assert d.regime == "international"


def test_continuation_pages_merge_without_artifacts():
    docs = docs_from("handbook-annex-sample.txt")
    for d in docs:
        assert "CONTINUED" not in d.prose
        assert "(continued)" not in d.prose.lower()


def test_annexes_1_to_4_parsed_and_stops_before_interpretative_rules():
    docs = docs_from("handbook-annex-sample.txt")
    annexes = [d.number for d in docs if d.number.startswith("Annex")]
    assert annexes == ["Annex I", "Annex II", "Annex III", "Annex IV"]
    a1 = next(d for d in docs if d.number == "Annex I")
    assert a1.title == "Positioning and Technical Details of Lights and Shapes"
    assert len(a1.prose) > 2000
    assert not any("INTERPRETATIVE" in d.prose for d in docs)
