"""Golden cases: the production chokepoint's decisions, preserved as
graph behavior. Offline — the stub provider stands in for transports.

Run: python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gd_graph.graph import build_graph, run_once  # noqa: E402
from gd_graph.provider import StubProvider  # noqa: E402


class GraphCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = os.path.join(self.tmp, "ledger.jsonl")
        self.graph = build_graph(provider=StubProvider(), ledger_path=self.ledger)

    def rows(self):
        if not os.path.exists(self.ledger):
            return []
        with open(self.ledger) as fh:
            return [line for line in fh if line.strip()]

    def test_happy_path_approves_and_books(self):
        out = run_once(self.graph, prompt="status?", routing_class="qr-coding-burst",
                       provider="local", model="qwen3:14b",
                       required_terms=["lane live"], thread_id="a", approve=True)
        self.assertEqual(out["status"], "approved")
        self.assertTrue(out["ticket"].startswith("GD-"))
        self.assertEqual(len(self.rows()), 1)

    def test_gate_rejection_is_a_row(self):
        out = run_once(self.graph, prompt="status?", routing_class="qr-coding-burst",
                       provider="local", model="qwen3:14b",
                       required_terms=["lane live"], thread_id="b", approve=False)
        self.assertEqual(out["status"], "rejected-gate")
        self.assertEqual(len(self.rows()), 1)

    def test_unanswered_gate_books_nothing(self):
        out = run_once(self.graph, prompt="status?", routing_class="qr-coding-burst",
                       provider="local", model="qwen3:14b",
                       required_terms=["lane live"], thread_id="c", approve=None)
        self.assertEqual(out["status"], "awaiting-approval")
        self.assertEqual(self.rows(), [])

    def test_class_mismatch_blocks_by_name(self):
        out = run_once(self.graph, prompt="x", routing_class="qr-coding-burst",
                       provider="anthropic", model="claude-opus", thread_id="d")
        self.assertEqual(out["status"], "blocked-router:class-mismatch")
        self.assertEqual(len(self.rows()), 1)

    def test_test0_compartmented_fails_closed(self):
        out = run_once(self.graph, prompt="x", routing_class="qr-research",
                       provider="google", model="gemini-flash",
                       sensitivity="compartmented", thread_id="e")
        self.assertEqual(out["status"], "blocked-router:test-0")

    def test_geneva_direct_blocks_frontier(self):
        out = run_once(self.graph, prompt="x", routing_class="qr-quick-lookup",
                       provider="anthropic", model="claude-sonnet", thread_id="f")
        self.assertEqual(out["status"], "blocked-router:geneva-direct")

    def test_verification_failure_never_gates(self):
        graph = build_graph(provider=StubProvider(text="unrelated filler"),
                            ledger_path=self.ledger)
        out = run_once(graph, prompt="x", routing_class="qr-coding-burst",
                       provider="local", model="qwen3:14b",
                       required_terms=["lane live"], thread_id="g", approve=True)
        self.assertEqual(out["status"], "rejected-verification")
        self.assertEqual(len(self.rows()), 1)


if __name__ == "__main__":
    unittest.main()
