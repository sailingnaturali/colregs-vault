from audit.checks import CheckItem
from audit.report import render


def _item(rid):
    return CheckItem("sightings.yaml", rid, "fishing", "sig", "Annex II 2(a)(ii)", "prose")


def _v(verdict, fix=""):
    return {"verdict": verdict, "confidence": 1.0, "reason": "r", "suggested_fix": fix}


def test_render_splits_consensus_from_single_model_flags():
    results = [
        (_item("agree-ok"), {"a": _v("ok"), "b": _v("ok"), "c": _v("ok")}),        # not flagged
        (_item("one-dissent"), {"a": _v("ok"), "b": _v("ok"), "c": _v("wrong", "X")}),  # 1 wrong
        (_item("two-agree-wrong"), {"a": _v("wrong", "Y"), "b": _v("wrong", "Y"), "c": _v("ok")}),  # 2 wrong
    ]
    out = render(results, ["a", "b", "c"], "2026-07-13")
    consensus, single = out.split("## Single-model flags")[0], out.split("## Single-model flags")[1]

    # unanimous-ok row appears in neither flag section
    assert "agree-ok" not in out.split("## Model agreement")[0]
    # the 2-wrong row is a consensus concern; the 1-wrong row is only a single-model flag
    assert "two-agree-wrong" in consensus and "two-agree-wrong" not in single.split("## Model agreement")[0]
    assert "one-dissent" in single and "one-dissent" not in consensus
    # header counts and the per-row wrong tally
    assert "1 consensus concern(s)" in out
    assert "1 single-model flag(s)" in out
    assert "(2/3 wrong)" in out and "(1/3 wrong)" in out
    assert "suggest `Y`" in out
    # agreement summary preserved (a wrong only on two-agree-wrong; c wrong only on one-dissent)
    assert "a: ok 2, wrong 1, unsure 0" in out
    assert "c: ok 2, wrong 1, unsure 0" in out


def test_render_reports_no_consensus_when_all_flags_are_solo():
    results = [
        (_item("solo"), {"a": _v("ok"), "b": _v("ok"), "c": _v("wrong")}),
    ]
    out = render(results, ["a", "b", "c"], "2026-07-13")
    assert "0 consensus concern(s)" in out
    assert "no row was flagged wrong by 2 or more models" in out
    assert "solo" in out.split("## Single-model flags")[1]
