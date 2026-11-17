"""Verification: deterministic checks on a completion before it can
reach the approval gate. A completion that fails verification is
recorded in the ledger as rejected and never gated.

Ported from gated_dispatch/verify.py — the checks and the anchored-term
rule are the production ones.
"""

from dataclasses import dataclass, field


@dataclass
class Verification:
    passed: bool
    checks: dict = field(default_factory=dict)


def _anchored(term: str, text: str) -> bool:
    """A term is anchored when it appears as the whole text, as a
    standalone line, at a line start, or on a labeled verdict line —
    not merely as a substring buried in filler."""
    stripped = text.strip()
    if stripped == term:
        return True
    for line in text.splitlines():
        line = line.strip()
        if line == term or line.startswith(term):
            return True
        if line.lower().startswith("verdict:") and term in line:
            return True
    return False


def verify_completion(text: str, required_terms=(), max_chars: int = 20000) -> Verification:
    checks = {
        "non_empty": bool(text and text.strip()),
        "within_size": len(text) <= max_chars,
    }
    for term in required_terms:
        checks[f"term:{term}"] = _anchored(term, text)
    return Verification(passed=all(checks.values()), checks=checks)
