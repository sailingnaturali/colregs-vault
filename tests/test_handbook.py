from pathlib import Path

from colregs_build.handbook import (international_pages, split_pages,
                                    strip_figure_captions)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return split_pages((FIXTURES / name).read_text())


def test_strip_figure_captions_removes_captions_keeps_prose():
    text = (
        "(v) when the length of the tow exceeds 200 meters, a diamond shape where\n"
        "it can best be seen.\n"
        "\n"
        "Power-driven vessel towing astern—towing vessel less than 50 meters in length;\n"
        "length of tow exceeds 200 meters.\n"
        "Same for Inland\n"
        "\n"
        "Vessel aground. Same for Inland.\n"
        "\n"
        "(a) A vessel at anchor shall exhibit where it can best be seen:\n"
        "\n"
        "Power-driven vessel pushing ahead or towing alongside—\n"
        "towing vessel less than 50 meters in length.\n"
        "International only.\n"
        "(d) A power-driven vessel to which paragraph (a) applies shall comply.\n"
        "\n"
        "Vessel proceeding under sail when also being propelled by\n"
        "machinery. Same for Inland except that a vessel of less than\n"
        "12 meters in length is not required to exhibit the dayshape.\n"
    )
    out = strip_figure_captions(text)
    # tag mid-line with caption text continuing after it -> whole block dropped
    assert "Vessel proceeding under sail" not in out
    assert "not required to exhibit the dayshape" not in out
    assert "Power-driven vessel towing astern" not in out   # multi-line caption gone
    assert "length of tow exceeds 200 meters." not in out.split("diamond shape")[1]
    assert "Vessel aground" not in out                       # single-line caption gone
    assert "Power-driven vessel pushing ahead" not in out    # caption sandwiched above prose
    assert "International only" not in out
    assert "Same for Inland" not in out
    assert "a diamond shape where\nit can best be seen." in out   # prose survives
    assert "(a) A vessel at anchor" in out                       # prose survives
    assert "(d) A power-driven vessel to which paragraph (a) applies" in out  # prose after caption survives


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


def test_section_heading_fragments_do_not_leak_into_prose():
    docs = docs_from("handbook-rules-sample.txt")
    by = {d.number: d for d in docs}
    # Section I's wrapped heading line must not pollute Rule 3
    assert "Condition of Visibility" not in by["3"].prose
