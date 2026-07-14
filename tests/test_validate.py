from colregs_build import validate as build_vault
from colregs_build.model import RuleDoc


def full_set():
    docs = []
    for regime, numbers in build_vault.EXPECTED.items():
        for n in numbers:
            docs.append(RuleDoc(number=n, regime=regime, title="T",
                                prose="(a) Synthetic body text comfortably above the short-prose threshold."))
    return docs


def test_complete_set_validates_clean():
    assert build_vault.validate(full_set()) == []


def test_missing_rule_is_reported():
    docs = [d for d in full_set() if not (d.regime == "canadian" and d.number == "40")]
    errors = build_vault.validate(docs)
    assert any("canadian" in e and "40" in e for e in errors)


def test_unexpected_number_is_reported():
    docs = full_set() + [RuleDoc(number="99", regime="inland", title="T", prose="x")]
    assert any("99" in e for e in build_vault.validate(docs))


def test_artifacts_and_empty_prose_are_reported():
    docs = full_set()
    docs[0].prose = "text Rule 9—CONTINUED text"
    docs[1].prose = "   "
    errors = build_vault.validate(docs)
    assert any("artifact" in e for e in errors)
    assert any("empty" in e for e in errors)


def test_reserved_stubs_are_allowed():
    docs = full_set()
    r28 = next(d for d in docs if d.regime == "inland" and d.number == "28")
    r28.prose = "[Reserved] — Rule 28 is reserved and contains no operative text."
    assert build_vault.validate(docs) == []
