"""Providers: an offline stub transport for tests and demos, and an
OpenAI-compatible HTTP transport built on the standard library — the
same two shapes the production dispatcher runs against.
"""

import json
import urllib.request


class StubProvider:
    """Deterministic offline provider. Echoes a canned completion and
    reports usage the way a real provider response would."""

    def __init__(self, text: str = "lane live", tokens_in: int = 19, tokens_out: int = 5):
        self.text = text
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out

    def complete(self, provider: str, model: str, prompt: str) -> dict:
        return {"text": self.text, "model_served": model,
                "tokens_in": self.tokens_in, "tokens_out": self.tokens_out}


class HttpProvider:
    """OpenAI-compatible chat completions over urllib (no SDK)."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def complete(self, provider: str, model: str, prompt: str) -> dict:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        usage = data.get("usage", {})
        return {
            "text": data["choices"][0]["message"]["content"],
            "model_served": data.get("model", model),
            "tokens_in": usage.get("prompt_tokens", 0),
            "tokens_out": usage.get("completion_tokens", 0),
        }
