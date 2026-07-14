from pathlib import Path

from audit.checks import build_checks, CheckItem

VAULT = Path(__file__).resolve().parent.parent


def test_build_checks_covers_both_sources_with_prose():
    items = build_checks(VAULT)
    assert items
    sources = {i.source for i in items}
    assert sources == {"requirements.yaml", "sightings.yaml"}
    # every resolvable citation carries loaded prose
    resolved = [i for i in items if i.rule_prose is not None]
    assert resolved and all(len(i.rule_prose) > 20 for i in resolved)


def test_build_checks_dedups_row_citation_pairs():
    items = build_checks(VAULT)
    keys = [(i.source, i.row_id, i.citation) for i in items]
    assert len(keys) == len(set(keys))          # no duplicate (row, citation)


def test_build_checks_has_known_row():
    items = build_checks(VAULT)
    hauling = [i for i in items
               if i.row_id == "fishing-hauling-night" and "Annex II" in i.citation]
    assert hauling and hauling[0].citation == "Annex II 2(a)(ii)"
