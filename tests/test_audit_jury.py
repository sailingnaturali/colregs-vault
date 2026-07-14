from audit.checks import CheckItem
from audit.jury import parse_verdict, get_verdict, run_jury


def _item(prose="(a) some rule text long enough to matter."):
    return CheckItem("sightings.yaml", "row1", "fishing",
                     "white+red [night]", "Annex II 2(a)(ii)", prose)


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
