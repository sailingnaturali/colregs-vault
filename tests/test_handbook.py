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
