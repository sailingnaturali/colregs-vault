from audit.checks import CheckItem
from audit.report import (_key, _mean_confidence, _weighted_risk, render)


def _item(rid, citation="Annex II 2(a)(ii)"):
    return CheckItem("sightings.yaml", rid, "fishing", "sig", citation, "prose")


def _v(verdict, conf=1.0, fix=""):
    return {"verdict": verdict, "confidence": conf, "reason": "r", "suggested_fix": fix}


def _sections(out):
    """Split rendered report into {header: text} by its ## sections."""
    parts, cur, buf = {}, "top", []
    for line in out.splitlines():
        if line.startswith("## "):
            parts[cur] = "\n".join(buf)
            cur, buf = line, []
        else:
            buf.append(line)
    parts[cur] = "\n".join(buf)
    return parts


def test_buckets_confirmed_consensus_single_and_blindspot():
    results = [
        (_item("agree-ok"), {"a": _v("ok"), "b": _v("ok"), "c": _v("ok")}),
        (_item("one-dissent"), {"a": _v("ok"), "b": _v("ok"), "c": _v("wrong", fix="X")}),
        (_item("two-agree-wrong"), {"a": _v("wrong", fix="Y"), "b": _v("wrong", fix="Y"), "c": _v("ok")}),
    ]
    out = render(results, ["a", "b", "c"], "2026-07-15")
    s = _sections(out)
    consensus = next(v for k, v in s.items() if k.startswith("## Consensus"))
    single = next(v for k, v in s.items() if k.startswith("## Single-model"))
    blind = next(v for k, v in s.items() if k.startswith("## Blind spots"))

    assert "two-agree-wrong" in consensus and "two-agree-wrong" not in single
    assert "one-dissent" in single and "one-dissent" not in consensus
    # unanimous-ok row is only a blind spot, never a flag
    assert "agree-ok" in blind and "agree-ok" not in consensus and "agree-ok" not in single
    assert "1 consensus" in out and "1 single-model" in out
    assert "risk 2.00" in consensus and "risk 1.00" in single  # weighted risk shown


def test_weight_orders_and_labels_rows():
    # two single-model flags: a low-weight juror's flag must rank below a trusted one's.
    results = [
        (_item("weak-flag"), {"lo": _v("wrong"), "hi": _v("ok")}),
        (_item("trusted-flag"), {"lo": _v("ok"), "hi": _v("wrong")}),
    ]
    weights = {"lo": 0.2, "hi": 1.0}
    out = render(results, ["lo", "hi"], "2026-07-15", weights=weights)
    single = next(v for k, v in _sections(out).items() if k.startswith("## Single-model"))
    assert single.index("trusted-flag") < single.index("weak-flag")   # higher risk first
    assert "risk 1.00" in single and "risk 0.20" in single
    assert "w=0.20" in out and "weight 1.00" in out                    # weights surfaced


def test_escalation_confirmed_promotes_a_single_flag_to_top():
    results = [(_item("lonely-but-right"), {"a": _v("ok"), "b": _v("wrong")})]
    escalations = {_key(_item("lonely-but-right")): {"claude": _v("wrong", fix="Z")}}
    out = render(results, ["a", "b"], "2026-07-15", escalations=escalations)
    s = _sections(out)
    confirmed = next(v for k, v in s.items() if k.startswith("## Escalation-confirmed"))
    single = next(v for k, v in s.items() if k.startswith("## Single-model"))
    assert "lonely-but-right" in confirmed and "lonely-but-right" not in single
    assert "escalation → claude" in confirmed
    assert "1 escalation-confirmed" in out


def test_blind_spots_ranked_by_ascending_confidence():
    results = [
        (_item("sure"), {"a": _v("ok", 0.99), "b": _v("ok", 0.99)}),
        (_item("shaky"), {"a": _v("ok", 0.30), "b": _v("ok", 0.40)}),
    ]
    out = render(results, ["a", "b"], "2026-07-15")
    blind = next(v for k, v in _sections(out).items() if k.startswith("## Blind spots"))
    assert blind.index("shaky") < blind.index("sure")   # least-sure first


def test_weighted_risk_and_mean_confidence_math():
    verdicts = {"a": _v("wrong", 0.5), "b": _v("ok", 1.0)}
    assert _weighted_risk(verdicts, {"a": 0.4, "b": 1.0}) == 0.2      # only wrong voters
    verdicts_ok = {"a": _v("ok", 0.2), "b": _v("ok", 0.8)}
    assert _mean_confidence(verdicts_ok, {"a": 1.0, "b": 1.0}) == 0.5
