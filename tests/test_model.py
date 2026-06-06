from pathlib import Path

from colregs_build.model import RuleDoc, write_doc


def make_doc(prose="(a) Alpha.\n\n(b) Bravo."):
    return RuleDoc(number="5", regime="inland", part="B", title="Look-out",
                   source_url="https://example.test/x.xml", retrieved="2026-06-06",
                   prose=prose)


def test_filename_zero_pads_rules_and_maps_annexes():
    assert make_doc().filename() == "rule-05.md"
    annex = RuleDoc(number="Annex III", regime="inland", title="T")
    assert annex.filename() == "annex-3.md"


def test_to_markdown_roundtrips_through_colregs_mcp_format():
    md = make_doc().to_markdown()
    assert md.startswith("---\n")
    head, fm, body = md.split("---", 2)
    import yaml
    meta = yaml.safe_load(fm)
    assert meta["number"] == "5"
    assert meta["verified"] is False
    assert body.lstrip("\n").startswith("(a)")


def test_write_doc_preserves_verified_only_when_prose_unchanged(tmp_path):
    rules = tmp_path / "rules"
    old: dict[Path, str] = {}
    p = write_doc(make_doc(), rules, old)
    # simulate a human flipping verified: true after review
    p.write_text(p.read_text().replace("verified: false", "verified: true"))
    old = {p: p.read_text()}
    p.unlink()
    p2 = write_doc(make_doc(), rules, old)            # same prose
    assert "verified: true" in p2.read_text()
    p2.unlink()
    p3 = write_doc(make_doc(prose="(a) Changed."), rules, old)  # changed prose
    assert "verified: false" in p3.read_text()
