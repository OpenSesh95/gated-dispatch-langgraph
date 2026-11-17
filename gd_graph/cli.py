"""CLI: run one ticket through the graph, offline by default.

    python -m gd_graph.cli --prompt "say lane live" --class qr-coding-burst \
        --provider local --model qwen3:14b --require "lane live" --yes

Without --yes the run pauses at the gate interrupt and books nothing —
the fail-closed rule, in framework idiom.
"""

import argparse

from .graph import build_graph, run_once


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gated-dispatch-graph")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--class", dest="routing_class", default="qr-quick-lookup")
    ap.add_argument("--provider", default="local")
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument("--sensitivity", default="standard")
    ap.add_argument("--require", action="append", default=[])
    ap.add_argument("--ledger", default="ledger.jsonl")
    ap.add_argument("--yes", action="store_true",
                    help="explicit opt-in: approve at the gate (recorded choice)")
    args = ap.parse_args(argv)
    graph = build_graph(ledger_path=args.ledger)
    out = run_once(graph, prompt=args.prompt, routing_class=args.routing_class,
                   provider=args.provider, model=args.model,
                   sensitivity=args.sensitivity, required_terms=args.require,
                   approve=True if args.yes else None)
    print(out.get("status"), out.get("ticket", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
