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


def test_requirements_items_carry_condition_and_length():
    items = build_checks(VAULT)
    power = next(i for i in items if i.row_id == "power-under-50m-night")
    assert power.condition == "night"
    assert power.length == "under 50 m"


def test_full_signal_holds_the_whole_multi_shape_arrangement():
    # aground-day is three balls; a single deduped item must still carry all three
    items = build_checks(VAULT)
    aground = next(i for i in items if i.row_id == "aground-day")
    assert aground.full_signal.count("ball") >= 3          # not just the first ball
    # fishing-day is two cones apexes together — both must be in the context
    fishing = next(i for i in items if i.row_id == "fishing-day")
    assert "apex downward" in fishing.full_signal and "apex upward" in fishing.full_signal


def test_paired_shapes_sharing_a_citation_are_one_combined_element():
    # fishing-day is two cones apexes-together, both citing Rule 26(c)(i); the single
    # item for that citation must carry BOTH cones so the shape is judged as a unit,
    # not just the first cone in isolation.
    items = build_checks(VAULT)
    fishing = [i for i in items
               if i.row_id == "fishing-day" and i.citation == "Rule 26(c)(i)"]
    assert len(fishing) == 1                                    # still one item per (row, citation)
    desc = fishing[0].signal_desc
    assert "apex downward" in desc and "apex upward" in desc    # both cones combined


def test_light_options_render_as_alternatives_not_flattened():
    # sailing-under-20m-night is (sidelights + sternlight) OR (tricolor) — either/or,
    # so the context must not read as all shown at once.
    items = build_checks(VAULT)
    sailing = next(i for i in items if i.row_id == "sailing-under-20m-night")
    assert "one of:" in sailing.full_signal
    assert " OR " in sailing.full_signal


def test_sightings_full_signal_is_the_observed_arrangement():
    items = build_checks(VAULT)
    cones = next(i for i in items if i.row_id == "fishing-cones-day")
    assert cones.condition == "day"
    assert "cone_down" in cones.full_signal and "cone_up" in cones.full_signal
