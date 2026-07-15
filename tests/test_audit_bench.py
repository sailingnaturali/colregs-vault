from pathlib import Path

from audit.bench import (BenchScore, CORRECT, WRONG, adopt_verdict, bench_cases,
                         load_corpus, regressions, run_corpus, weights_from_scores)

VAULT = Path(__file__).resolve().parent.parent


def _v(verdict, conf=1.0):
    return {"verdict": verdict, "confidence": conf, "reason": "", "suggested_fix": ""}


def _mk(rid, cite):
    from audit.checks import CheckItem
    return CheckItem("sightings.yaml", rid, "s", "sig", cite, "prose")


def test_bench_cases_are_labeled_and_prose_loaded():
    cases = bench_cases(VAULT)
    assert len(cases) == len(CORRECT) + len(WRONG)
    oks = [c for c, e in cases if e == "ok"]
    wrongs = [(c, e) for c, e in cases if e == "wrong"]
    assert len(oks) == len(CORRECT) and len(wrongs) == len(WRONG)
    # a corrupted case must carry the bad citation and the prose for it (not None)
    for item, _ in wrongs:
        assert item.rule_prose is not None
        assert (item.row_id, item.citation) in WRONG


def test_corpus_loads_from_yaml():
    correct, wrong = load_corpus()
    assert (correct, wrong) == (CORRECT, WRONG)
    assert all(len(row) == 2 for row in correct + wrong)  # (row_id, citation) tuples


def test_weight_math_and_floor():
    # perfect: catch all, no false positives -> weight 1.0
    assert BenchScore(n_ok=2, n_wrong=2, false_pos=0, caught=2).weight == 1.0
    # useless: catches nothing, flags everything -> floored, not zero
    assert BenchScore(n_ok=2, n_wrong=2, false_pos=2, caught=0).weight == 0.1
    # half catch, no false pos -> 0.5*0.5 + 0.5*1.0 = 0.75
    assert BenchScore(n_ok=2, n_wrong=2, false_pos=0, caught=1).weight == 0.75


def test_run_corpus_scores_each_model_from_its_verdicts():
    cases = bench_cases(VAULT)
    good = lambda s, u: '{"verdict":"wrong","confidence":1}'   # noqa: E731 — flags everything
    # a client that flags everything: catches all wrong cases, false-positives every ok case
    scores, table = run_corpus({"trigger": good}, VAULT)
    s = scores["trigger"]
    assert s.caught == s.n_wrong and s.false_pos == s.n_ok
    assert len(table) == len(cases)


def test_regressions_flags_when_weighted_jury_flips():
    ok_item, wrong_item = _mk("r1", "Rule 1"), _mk("r2", "Rule 2")
    # jury correctly passes the ok case and catches the wrong case -> no regression
    good_table = [
        (ok_item, "ok", {"a": _v("ok"), "b": _v("ok")}),
        (wrong_item, "wrong", {"a": _v("wrong"), "b": _v("wrong")}),
    ]
    assert regressions(good_table, {"a": 1.0, "b": 1.0}, threshold=1.0) == []
    # now the jury misses the wrong case (both say ok) -> one regression
    bad_table = [(wrong_item, "wrong", {"a": _v("ok"), "b": _v("ok")})]
    reg = regressions(bad_table, {"a": 1.0, "b": 1.0}, threshold=1.0)
    assert len(reg) == 1 and reg[0][0] is wrong_item


def test_adopt_verdict_thresholds():
    jury = {"j": BenchScore(2, 2, 0, 1)}   # weight 0.75 -> median 0.75
    assert weights_from_scores(jury) == {"j": 0.75}
    assert adopt_verdict(BenchScore(2, 2, 0, 2), jury)[0] == "adopt"      # 1.0 >= 0.75
    assert adopt_verdict(BenchScore(2, 2, 0, 1), jury)[0] == "adopt"      # 0.75 == median
    assert adopt_verdict(BenchScore(4, 4, 1, 2), jury)[0] == "probation"  # 0.625 in [0.6,0.75)
    assert adopt_verdict(BenchScore(2, 2, 2, 0), jury)[0] == "reject"     # 0.1 floor < 0.6
