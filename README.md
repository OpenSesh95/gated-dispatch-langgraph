# gated-dispatch-langgraph

**The gated-dispatch control loop, re-expressed as a LangGraph stateful graph.**

[gated-dispatch](https://github.com/OpenSesh95/gated-dispatch) is a hand-rolled,
standard-library-only dispatch pipeline that runs in production: every model
call is routed by class, checked by deterministic verification, stopped at a
fail-closed human approval gate, and metered into a cost ledger — including
the failures. This repo rebuilds the same loop in LangGraph idiom, node for
node, to answer one question honestly: *what does the framework actually
change, and what does it leave alone?*

## The narrative

I built the dispatcher custom first — no framework — because the control loop
was the point: routing rules enforced at one chokepoint, verification before
any human saw output, a gate that could not pass silently, and a ledger that
kept the failures. Then I mapped it to LangGraph. The mapping turned out to be
unusually clean, and the places where it is *not* clean are the interesting
part:

- The **gate is an interrupt**. LangGraph's `interrupt()` + checkpointing is
  the first framework primitive I have used that matches the production rule
  exactly: the run pauses with the verified completion in state, and nothing
  books until a human resumes it with an explicit decision. An unanswered
  gate books nothing — the production EOF rule, in framework idiom.
- The **ledger is not the checkpoint**. Checkpoints hold resumable state;
  the JSONL ledger holds the publishable receipt (prompt hashes, never raw
  prompts; usage from the provider's own response fields). The graph keeps
  both, for different readers.
- **Routing stays a table, not a prompt.** The router is a deterministic
  class table with named blocks (`blocked-router:class-mismatch`,
  `blocked-router:test-0`, …). LangGraph conditional edges carry the
  decisions; they do not make them.

## Mapping table

| gated-dispatch (custom) | This repo (LangGraph) |
|---|---|
| `cli.run` control loop | `StateGraph` — `gd_graph/graph.py` |
| Query Routing Table chokepoint | `route` node + conditional edge (`after_route`) |
| Class chains, named blocks | `gd_graph/routing.py` (representative slice of the table) |
| Provider transports (stub / OpenAI-compatible HTTP) | `gd_graph/provider.py`, called by the `dispatch` node |
| `verify.py` — deterministic checks, anchored terms | `verify` node — `gd_graph/verify.py`, ported unchanged |
| `gate.py` — explicit yes or `GateRejected` | `gate` node — `interrupt()` + `Command(resume=...)` |
| `ledger.py` — one JSONL row per run, any outcome | `ledger` node — `gd_graph/ledger.py`; blocked, rejected, and failed runs are rows too |
| STD-0 ticket fields | `TicketState` — the graph's state schema |
| Test suite (stub transport, offline) | `tests/test_graph.py` — the chokepoint's golden decisions as graph behavior |

## Quickstart

```bash
pip install -e .
# offline demo: stub provider, explicit gate opt-in
python -m gd_graph.cli --prompt "say lane live" --class qr-coding-burst \
    --provider local --model qwen3:14b --require "lane live" --yes
# without --yes the run pauses at the gate and books nothing
python -m unittest discover -s tests -v
```

## What this slice leaves out

The production routing table is larger and carries governance the slice does
not reproduce; the slice ships a representative four-class table with the
same rules. Budget envelopes, provider failover chains, and the masking seam
stay in the production system. This repo is the framework mapping, kept
deliberately small enough to audit in one sitting.

## License

MIT
