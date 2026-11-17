"""Routing: a representative slice of the production Query Routing Table.

The production table routes every dispatch by class. A class admits a
chain of (provider, model) pairs, cheapest capable first. The rules
re-expressed here are the rules the production chokepoint enforces:

- A requested (provider, model) outside the class's admitted set stops
  by name: blocked-router:class-mismatch.
- Geneva-direct classes admit no frontier dispatch; a frontier request
  under one stops as blocked-router:geneva-direct.
- TEST-0: an input whose data sensitivity is "compartmented" fails
  closed to local lanes only. No degrade, no substitution.
- The ad-hoc class is a latency bypass: local requests proceed stamped
  as the bypass class; frontier requests stop as blocked-router:b7-bypass.
- An unknown class id falls back to qr-quick-lookup, stamped
  unclassified (the table face rule).

Local-estate models are admitted on every class: the home lanes are
always the cheapest capable.
"""

from dataclasses import dataclass, field

TABLE_VERSION = "slice-0.1"

LOCAL_PROVIDERS = frozenset({"local", "gcp"})

# class_id -> (chain of (provider, model), geneva_direct?)
CLASSES = {
    "qr-quick-lookup": ([("local", "llama3.1:8b")], True),
    "qr-life-ops": ([("local", "llama3.1:8b")], True),
    "qr-coding-burst": (
        [("openrouter", "north-mini-code"), ("local", "qwen3:14b"),
         ("anthropic", "claude-sonnet")],
        False,
    ),
    "qr-research": (
        [("google", "gemini-flash"), ("local", "deepseek-r1:14b"),
         ("openrouter", "nemotron-3-ultra"), ("anthropic", "claude-opus")],
        False,
    ),
    "ad-hoc": ([("local", "llama3.1:8b")], True),
}

FALLBACK_CLASS = "qr-quick-lookup"


@dataclass
class RouteDecision:
    admitted: bool
    lane: str = ""
    provider: str = ""
    model: str = ""
    position: int = -1
    blocked_reason: str = ""
    unclassified: bool = False
    routing_class: str = ""
    stamp: dict = field(default_factory=dict)


def route(routing_class: str, provider: str, model: str,
          sensitivity: str = "standard") -> RouteDecision:
    """Decide whether (provider, model) may run under routing_class."""
    unclassified = routing_class not in CLASSES
    cls = FALLBACK_CLASS if unclassified else routing_class
    chain, geneva_direct = CLASSES[cls]
    is_local = provider in LOCAL_PROVIDERS

    def blocked(reason: str) -> RouteDecision:
        return RouteDecision(
            admitted=False, blocked_reason=reason, unclassified=unclassified,
            routing_class=cls,
            stamp={"table_version": TABLE_VERSION, "class": cls,
                   "blocked": reason, "unclassified": unclassified})

    # TEST-0 binds first: compartmented data never leaves the local estate.
    if sensitivity == "compartmented" and not is_local:
        return blocked("blocked-router:test-0")
    if cls == "ad-hoc":
        if not is_local:
            return blocked("blocked-router:b7-bypass")
        return RouteDecision(
            admitted=True, lane="bypass", provider=provider, model=model,
            position=0, routing_class=cls,
            stamp={"table_version": TABLE_VERSION, "class": cls,
                   "lane": "bypass", "position": 0, "unclassified": False})
    if geneva_direct and not is_local:
        return blocked("blocked-router:geneva-direct")
    if is_local:
        return RouteDecision(
            admitted=True, lane="local", provider=provider, model=model,
            position=0, routing_class=cls,
            stamp={"table_version": TABLE_VERSION, "class": cls,
                   "lane": "local", "position": 0,
                   "unclassified": unclassified})
    for i, (p, m) in enumerate(chain):
        if (p, m) == (provider, model):
            return RouteDecision(
                admitted=True, lane="frontier" if i == len(chain) - 1 else "chain",
                provider=p, model=m, position=i, routing_class=cls,
                stamp={"table_version": TABLE_VERSION, "class": cls,
                       "lane": "frontier" if i == len(chain) - 1 else "chain",
                       "position": i, "unclassified": unclassified})
    return blocked("blocked-router:class-mismatch")
