"""Cost ledger: one JSONL row per run, whatever the outcome.

Rows record the prompt's SHA-256 and length, never the raw prompt, so
a ledger can be published as an ops receipt without leaking content.
Token counts come from the provider response's own usage fields; cost
is computed at published list rates. Refusals and holds are rows too.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

# USD per 1M tokens (input, output) — published list rates, slice subset.
PRICES = {
    "claude-sonnet": (3.00, 15.00),
    "claude-opus": (15.00, 75.00),
    "gemini-flash": (0.30, 2.50),
    "north-mini-code": (0.00, 0.00),
    "nemotron-3-ultra": (0.00, 0.00),
    "llama3.1:8b": (0.00, 0.00),
    "qwen3:14b": (0.00, 0.00),
    "deepseek-r1:14b": (0.00, 0.00),
}


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    rate = PRICES.get(model)
    if rate is None:
        return 0.0
    return round((tokens_in * rate[0] + tokens_out * rate[1]) / 1_000_000, 6)


def _next_ticket_id(path: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    n = 0
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            n = sum(1 for _ in fh)
    return f"GD-{day}-{n + 1:04d}"


def append_row(path: str, *, prompt: str, model: str, model_served: str,
               tokens_in: int, tokens_out: int, status: str,
               checks: dict | None = None, routing: dict | None = None) -> dict:
    row = {
        "ticket": _next_ticket_id(path),
        "ts": datetime.now(timezone.utc).isoformat(),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "prompt_chars": len(prompt),
        "model_requested": model,
        "model_served": model_served,
        "model_mismatch": bool(model_served and model_served != model),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": estimate_cost_usd(model, tokens_in, tokens_out),
        "status": status,
        "checks": checks or {},
        "routing": routing or {},
    }
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row
