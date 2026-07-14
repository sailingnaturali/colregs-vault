from pathlib import Path

from audit.bench import bench_cases, CORRECT, WRONG

VAULT = Path(__file__).resolve().parent.parent


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
