from pathlib import Path

from audit.refs import ref_to_file, load_rule_prose

VAULT = Path(__file__).resolve().parent.parent


def test_ref_to_file_maps_rules_and_annexes():
    assert ref_to_file("Rule 24(a)(i)") == "rule-24.md"
    assert ref_to_file("Annex II 2(a)(ii)") == "annex-2.md"
    assert ref_to_file("Rule 30(b)") == "rule-30.md"
    assert ref_to_file("nonsense") is None


def test_load_rule_prose_strips_frontmatter():
    prose = load_rule_prose(VAULT, "Rule 30(b)")
    assert prose is not None
    assert prose.startswith("(a) A vessel at anchor")
    assert "verified:" not in prose          # frontmatter gone


def test_load_rule_prose_missing_file_is_none():
    assert load_rule_prose(VAULT, "Rule 99") is None
