"""Run each check item across each model client and collect structured verdicts."""
from __future__ import annotations

import json
from typing import Callable

from audit.checks import CheckItem

Client = Callable[[str, str], str]

SYSTEM = (
    "You verify a single navigation-rules citation. You are given the exact text of the "
    "cited rule and a claim mapping a vessel situation / observed signal to that citation. "
    "Decide whether the cited rule — and its specific sub-paragraph — supports the claim. "
    'Respond ONLY as JSON: {"verdict":"ok|wrong|unsure","confidence":0-1,"reason":"...",'
    '"suggested_fix":"<corrected citation, or empty>"}. If the cited paragraph does not '
    'support the claim, verdict is "wrong" and put the correct citation in suggested_fix.'
)

_VERDICTS = {"ok", "wrong", "unsure"}


def build_prompt(item: CheckItem) -> tuple[str, str]:
    prose = item.rule_prose or "(cited rule text not found)"
    context = [f"situation: {item.situation}"]
    if item.condition:
        context.append(f"condition: {item.condition}")
    if item.length:
        context.append(f"vessel length: {item.length}")
    if item.full_signal:
        context.append(f"full signal shown for this row: {item.full_signal}")
    user = (f"RULE TEXT:\n{prose}\n\nROW CONTEXT:\n" + "\n".join(context)
            + f"\n\nCLAIM:\nthe element «{item.signal_desc}» is cited as {item.citation}.\n"
            "Is that citation, and its sub-paragraph, correct for that element within the "
            "full signal above? Judge the element in the context of the whole signal, not in "
            "isolation.")
    return SYSTEM, user


def parse_verdict(text: str) -> dict | None:
    try:
        d = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(d, dict):
        return None
    verdict = d.get("verdict", "unsure")
    if verdict not in _VERDICTS:
        verdict = "unsure"
    try:
        confidence = float(d.get("confidence", 0) or 0)
    except (ValueError, TypeError):
        confidence = 0.0
    return {"verdict": verdict, "confidence": confidence,
            "reason": str(d.get("reason", "")),
            "suggested_fix": str(d.get("suggested_fix", ""))}


def get_verdict(client: Client, item: CheckItem, retries: int = 1) -> dict:
    if item.rule_prose is None:
        return {"verdict": "wrong", "confidence": 1.0,
                "reason": "citation does not resolve to a rule file", "suggested_fix": ""}
    system, user = build_prompt(item)
    last_error = None
    for _ in range(retries + 1):
        try:
            parsed = parse_verdict(client(system, user))
        except Exception as e:  # noqa: BLE001 — any client/SDK error degrades to unsure
            last_error = e
            continue
        if parsed:
            return parsed
    reason = f"model error: {last_error}" if last_error else "unparseable model output"
    return {"verdict": "unsure", "confidence": 0.0, "reason": reason, "suggested_fix": ""}


def run_jury(items, clients: dict[str, Client]):
    results = []
    for item in items:
        verdicts = {name: get_verdict(fn, item) for name, fn in clients.items()}
        results.append((item, verdicts))
    return results
