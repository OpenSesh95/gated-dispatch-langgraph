"""The dispatch loop as a LangGraph stateful graph.

Production gated-dispatch runs: route -> dispatch -> verify -> gate ->
ledger, as a hand-rolled control loop. This module re-expresses the
same loop as a LangGraph StateGraph, node for node:

    intake -> route -> dispatch -> verify -> gate -> ledger -> END
                 |          |            |
                 +----------+------------+--> ledger (blocked / failed /
                                                    rejected are rows too)

The gate is a LangGraph interrupt: the graph pauses with the verified
completion in state and resumes only on an explicit human decision
(Command(resume=...)). There is no silent pass — an unanswered gate
leaves the run unbooked, exactly like the production EOF rule.

The checkpoint record is the ledger's twin: LangGraph checkpoints hold
the resumable state; the JSONL ledger holds the publishable receipt.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt

from .ledger import append_row
from .provider import StubProvider
from .routing import route
from .verify import verify_completion


class TicketState(TypedDict):
    # The run's request
    prompt: str
    routing_class: str
    sensitivity: str
    provider: str
    model: str
    required_terms: list
    # Conversation surface (langchain-core messages)
    messages: Annotated[list, add_messages]
    # Routing outcome
    admitted: bool
    blocked_reason: str
    routing_stamp: dict
    # Dispatch outcome (usage from the provider response itself)
    completion: str
    model_served: str
    tokens_in: int
    tokens_out: int
    # Verification outcome
    verified: bool
    checks: dict
    # Gate + ledger outcome
    status: str
    ticket: str


def build_graph(provider=None, ledger_path: str = "ledger.jsonl"):
    provider = provider or StubProvider()

    def intake(state: TicketState) -> dict:
        return {"messages": [HumanMessage(content=state["prompt"])],
                "status": "intake"}

    def route_node(state: TicketState) -> dict:
        d = route(state["routing_class"], state["provider"], state["model"],
                  state.get("sensitivity", "standard"))
        return {"admitted": d.admitted, "blocked_reason": d.blocked_reason,
                "routing_stamp": d.stamp, "status": "routed"}

    def dispatch_node(state: TicketState) -> dict:
        r = provider.complete(state["provider"], state["model"], state["prompt"])
        return {"completion": r["text"], "model_served": r["model_served"],
                "tokens_in": r["tokens_in"], "tokens_out": r["tokens_out"],
                "messages": [AIMessage(content=r["text"])], "status": "dispatched"}

    def verify_node(state: TicketState) -> dict:
        v = verify_completion(state["completion"], state.get("required_terms", ()))
        return {"verified": v.passed, "checks": v.checks, "status": "verified"}

    def gate_node(state: TicketState) -> dict:
        # The fail-closed gate, as an interrupt. The graph pauses here;
        # only an explicit resume value books an approval.
        decision = interrupt({
            "awaiting_approval": state["completion"],
            "checks": state["checks"],
            "model_served": state["model_served"],
        })
        approved = decision is True or (
            isinstance(decision, str) and decision.strip().lower() in ("y", "yes"))
        return {"status": "approved" if approved else "rejected-gate"}

    def ledger_node(state: TicketState) -> dict:
        status = state["status"]
        if not state.get("admitted", True):
            status = state["blocked_reason"] or "blocked-router"
        elif state.get("verified") is False:
            status = "rejected-verification"
        row = append_row(
            ledger_path, prompt=state["prompt"], model=state["model"],
            model_served=state.get("model_served", ""),
            tokens_in=state.get("tokens_in", 0),
            tokens_out=state.get("tokens_out", 0),
            status=status, checks=state.get("checks", {}),
            routing=state.get("routing_stamp", {}))
        return {"ticket": row["ticket"], "status": status}

    def after_route(state: TicketState) -> str:
        return "dispatch" if state["admitted"] else "ledger"

    def after_verify(state: TicketState) -> str:
        return "gate" if state["verified"] else "ledger"

    g = StateGraph(TicketState)
    g.add_node("intake", intake)
    g.add_node("route", route_node)
    g.add_node("dispatch", dispatch_node)
    g.add_node("verify", verify_node)
    g.add_node("gate", gate_node)
    g.add_node("ledger", ledger_node)
    g.add_edge(START, "intake")
    g.add_edge("intake", "route")
    g.add_conditional_edges("route", after_route, ["dispatch", "ledger"])
    g.add_edge("dispatch", "verify")
    g.add_conditional_edges("verify", after_verify, ["gate", "ledger"])
    g.add_edge("gate", "ledger")
    g.add_edge("ledger", END)
    return g.compile(checkpointer=MemorySaver())


def run_once(graph, *, prompt: str, routing_class: str, provider: str,
             model: str, sensitivity: str = "standard",
             required_terms=(), thread_id: str = "t-1",
             approve: bool | None = None) -> dict:
    """Run one ticket. approve=None leaves the gate open (the graph
    pauses at the interrupt); True/False resume it with a decision."""
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.invoke({
        "prompt": prompt, "routing_class": routing_class,
        "sensitivity": sensitivity, "provider": provider, "model": model,
        "required_terms": list(required_terms),
    }, config)
    if "__interrupt__" in state:
        if approve is None:
            return {"status": "awaiting-approval", "interrupt": state["__interrupt__"]}
        state = graph.invoke(Command(resume=approve), config)
    return state
