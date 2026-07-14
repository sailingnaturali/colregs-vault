"""Guard the hand-curated decision tables against dangling rule references.

`requirements.yaml` and `sightings.yaml` are hand-edited and safety-critical, yet
nothing else in this repo validates them (the parser tests only cover rules/*.md).
This asserts every `rule:` citation resolves to a rule/annex file that exists, and
that each parenthetical sub-paragraph token actually appears in that file.

# ponytail: catches dangling/typo'd refs (Rule 99, Rule 24(z)), NOT semantic
# misattribution — a citation pointing at the wrong-but-real paragraph (e.g. the
# old "hauling -> Annex II 2(b)" bug, where 2(b) exists) still passes. That's a
# line-by-line content review, not automation.
"""

import re
from pathlib import Path

import yaml

from audit.refs import ref_to_file

VAULT = Path(__file__).resolve().parent.parent
RULES = VAULT / "rules" / "international"  # the curated tables cite the International regime


def _iter_rule_refs(node):
    """Yield every value stored under a 'rule' key, anywhere in the structure."""
    if isinstance(node, dict):
        for key, val in node.items():
            if key == "rule" and isinstance(val, str):
                yield val
            else:
                yield from _iter_rule_refs(val)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_rule_refs(item)


def _collect_refs():
    refs = []
    for name in ("requirements.yaml", "sightings.yaml"):
        data = yaml.safe_load((VAULT / name).read_text())
        for ref in _iter_rule_refs(data):
            # "Rule 25(e)+23(a)" cites two rules
            for segment in ref.split("+"):
                refs.append((name, ref, segment.strip()))
    return refs


def test_every_rule_reference_resolves():
    refs = _collect_refs()
    assert refs, "no rule references found — did the YAML schema change?"
    for source, full_ref, segment in refs:
        filename = ref_to_file(segment)
        assert filename, f"{source}: unparseable rule reference {full_ref!r}"
        path = RULES / filename
        assert path.exists(), f"{source}: {full_ref!r} -> missing {path.name}"
        text = path.read_text()
        for token in re.findall(r"\([a-z0-9ivx]+\)", segment):
            assert token in text, (
                f"{source}: {full_ref!r} cites {token} but {path.name} has no such sub-paragraph"
            )


if __name__ == "__main__":
    test_every_rule_reference_resolves()
    print(f"OK — {len(_collect_refs())} rule references all resolve")
