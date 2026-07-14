from audit.checks import CheckItem
from audit.report import render


def _item(rid):
    return CheckItem("sightings.yaml", rid, "fishing", "sig", "Annex II 2(a)(ii)", "prose")


def _v(verdict, fix=""):
    return {"verdict": verdict, "confidence": 1.0, "reason": "r", "suggested_fix": fix}


def test_render_flags_and_ranks():
    results = [
        (_item("agree-ok"), {"a": _v("ok"), "b": _v("ok")}),          # not flagged
        (_item("split"), {"a": _v("ok"), "b": _v("wrong", "X")}),      # flagged (disagree)
        (_item("both-wrong"), {"a": _v("wrong", "Y"), "b": _v("wrong", "Y")}),  # flagged
    ]
    out = render(results, ["a", "b"], "2026-07-13")
    assert "agree-ok" not in out.split("## Model agreement")[0]     # unanimous ok omitted
    # both-wrong (2 wrong) ranks above split (1 wrong)
    assert out.index("both-wrong") < out.index("split")
    assert "suggest `X`" in out
    assert "## Model agreement" in out
    assert "2 of 3 rows flagged" in out
    assert "a: ok 2, wrong 1, unsure 0" in out
    assert "b: ok 1, wrong 2, unsure 0" in out
