# Changelog

## v0.1.0 — 2026-11-17

- Initial slice: the gated-dispatch loop as a LangGraph StateGraph —
  intake → route → dispatch → verify → gate (interrupt) → ledger.
- Representative four-class routing table with the production rules:
  class-mismatch, geneva-direct, TEST-0 fail-closed, ad-hoc bypass,
  unclassified fallback.
- Verification ported unchanged (anchored-term rule); ledger ported
  (SHA-256 prompt records, usage-field metering, one row per run).
- Golden-case suite: 7 tests, all passing, offline on the stub provider.
