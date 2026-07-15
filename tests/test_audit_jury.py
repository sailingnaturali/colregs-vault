from audit.checks import CheckItem
from audit.jury import parse_verdict, get_verdict, run_jury, build_prompt, escalate


def _item(prose="(a) some rule text long enough to matter."):
    return CheckItem("sightings.yaml", "row1", "fishing",
                     "white+red [night]", "Annex II 2(a)(ii)", prose)


def test_build_prompt_includes_full_row_context():
    item = CheckItem("requirements.yaml", "aground-day", "vessel_aground",
                     "ball, uppermost", "Rule 30(d)(ii)", "(d)(ii) three balls...",
                     condition="day", length="under 50 m",
                     full_signal="ball, uppermost; ball, middle; ball, lowest")
    _system, user = build_prompt(item)
    assert "condition: day" in user
    assert "vessel length: under 50 m" in user
    assert "ball, uppermost; ball, middle; ball, lowest" in user   # whole signal, not one ball
    assert "ball, uppermost" in user and "Rule 30(d)(ii)" in user  # the element under test


def test_parse_verdict_normalizes_and_rejects_junk():
    v = parse_verdict('{"verdict":"wrong","confidence":0.9,"reason":"r","suggested_fix":"X"}')
    assert v == {"verdict": "wrong", "confidence": 0.9, "reason": "r", "suggested_fix": "X"}
    assert parse_verdict("not json") is None
    bad = parse_verdict('{"verdict":"maybe"}')          # unknown verdict -> unsure
    assert bad["verdict"] == "unsure"


def test_get_verdict_retries_then_unsure():
    calls = {"n": 0}

    def flaky(system, user):
        calls["n"] += 1
        return "garbage"
    v = get_verdict(flaky, _item(), retries=1)
    assert v["verdict"] == "unsure"
    assert calls["n"] == 2                               # initial + one retry


def test_dangling_citation_is_wrong_without_calling_model():
    called = {"n": 0}

    def never(system, user):
        called["n"] += 1
        return "{}"
    v = get_verdict(never, _item(prose=None))
    assert v["verdict"] == "wrong" and called["n"] == 0


def test_parse_verdict_rejects_non_object_json():
    # Valid JSON but not an object should return None (triggering retry/unsure fallback)
    assert parse_verdict("null") is None
    assert parse_verdict("5") is None
    assert parse_verdict("[1,2]") is None
    assert parse_verdict('"hi"') is None


def test_run_jury_collects_per_model_verdicts():
    def ok_client(system, user):
        return '{"verdict":"ok","confidence":1,"reason":"","suggested_fix":""}'

    def wrong_client(system, user):
        return '{"verdict":"wrong","confidence":1,"reason":"bad","suggested_fix":"Y"}'
    results = run_jury([_item()], {"a": ok_client, "b": wrong_client})
    assert len(results) == 1
    _item_out, verdicts = results[0]
    assert verdicts["a"]["verdict"] == "ok"
    assert verdicts["b"]["verdict"] == "wrong"


def test_get_verdict_handles_client_exceptions():
    calls = {"n": 0}

    def raiser(system, user):
        calls["n"] += 1
        raise RuntimeError("boom")
    v = get_verdict(raiser, _item(), retries=1)
    assert v["verdict"] == "unsure"
    assert "model error" in v["reason"]
    assert calls["n"] == 2                               # initial + one retry


def test_escalate_reuses_jury_verdict_but_calls_fresh_escalator():
    calls = {"strong": 0, "held": 0}

    def strong(system, user):
        calls["strong"] += 1
        return '{"verdict":"wrong","confidence":1,"reason":"","suggested_fix":""}'

    def held(system, user):
        calls["held"] += 1
        return '{"verdict":"ok","confidence":1,"reason":"","suggested_fix":""}'

    # 'strong' already voted in the jury -> reuse; 'held' is escalate-only -> call once.
    jury_verdicts = {"strong": {"verdict": "ok", "confidence": 1.0,
                                "reason": "", "suggested_fix": ""}}
    out = escalate(_item(), jury_verdicts, {"strong": strong, "held": held})
    assert out["strong"]["verdict"] == "ok"      # reused the jury vote, not re-asked
    assert out["held"]["verdict"] == "ok"        # freshly called
    assert calls == {"strong": 0, "held": 1}
