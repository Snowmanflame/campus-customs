"""Wires the five agents into one fully connected team and runs the ticket loop.

Every agent gets an `ask_<teammate>` tool for each of the other four, so any
agent can delegate to any other. A delegation is refused if the target is
already in the current chain (no A -> B -> A loops) or the chain is MAX_DEPTH
deep; the refusal tells the caller to put the question in its report instead.
"""

from __future__ import annotations

from collections.abc import AsyncIterable

from pydantic_ai import (
    Agent,
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RunContext,
    UsageLimits,
)

from .accounting import accounting_agent
from .boss import boss_agent
from .customer_service import customer_service_agent
from .facilities import facilities_agent
from .inventory import inventory_agent
from .models import AgentName, BossDecision, EventKind, EventSink, TeamDeps
from .shared import CAMPUS_MCP, mcp_call, reset_database

AGENTS: dict[AgentName, Agent] = {
    AgentName.boss: boss_agent,
    AgentName.inventory: inventory_agent,
    AgentName.accounting: accounting_agent,
    AgentName.facilities: facilities_agent,
    AgentName.customer_service: customer_service_agent,
}

DELEGATE_DESCRIPTIONS: dict[AgentName, str] = {
    AgentName.boss: "Escalate to the Boss for a decision only the Boss can make (priorities, discounts, final calls).",
    AgentName.inventory: "Ask Inventory about stock by SKU + size, shortfalls, which vendor can restock and when, or to draft a restock PO.",
    AgentName.accounting: "Ask Accounting about cash, invoices, overdue bills, margins/discounts, or to prepare a vendor payment for human approval.",
    AgentName.facilities: "Ask Facilities about the lease, rent amount and due date, or to prepare a rent payment for human approval.",
    AgentName.customer_service: "Ask Customer Service to draft a message to the requester. Give them every fact the message needs.",
}

MAX_DEPTH = 3  # boss -> specialist -> specialist
TICKET_USAGE_LIMITS = UsageLimits(request_limit=80, tool_calls_limit=120)


def _clip(value, limit: int = 600) -> str:
    text = value if isinstance(value, str) else repr(value)
    return text if len(text) <= limit else text[:limit] + "..."


async def _log_tool_events(ctx: RunContext[TeamDeps], events: AsyncIterable[AgentStreamEvent]) -> None:
    """Stream each MCP tool call/result of an agent run onto the activity feed."""
    async for event in events:
        if isinstance(event, FunctionToolCallEvent):
            name = event.part.tool_name
            if not name.startswith("ask_"):
                await ctx.deps.emit(EventKind.tool_call, f"{name}({_clip(event.part.args, 300)})",
                                    tool=name, args=event.part.args_as_dict())
        elif isinstance(event, FunctionToolResultEvent):
            name = getattr(event.part, "tool_name", "")
            if not name.startswith("ask_"):
                part = event.part
                text = part.model_response_str() if hasattr(part, "model_response_str") else getattr(part, "content", "")
                await ctx.deps.emit(EventKind.tool_result, f"{name} -> {_clip(text)}", tool=name)


def _make_delegate(target: AgentName):
    async def delegate(ctx: RunContext[TeamDeps], request: str) -> str:
        """Hand a self-contained request to a teammate and get their structured report back.

        Args:
            request: What you need, including the ticket id and every fact the teammate needs.
        """
        caller = ctx.deps.me
        if target in ctx.deps.chain:
            msg = (f"{target.value} is already working on this ticket further up the chain and is waiting on you. "
                   f"Put your question in questions_for_boss / your report instead.")
            await ctx.deps.emit(EventKind.delegation_refused, f"{caller.value} -> {target.value}: loop prevented")
            return msg
        if len(ctx.deps.chain) >= MAX_DEPTH:
            await ctx.deps.emit(EventKind.delegation_refused, f"{caller.value} -> {target.value}: max depth")
            return f"Delegation depth limit reached; you cannot ask {target.value}. Finish with what you have and note the gap."

        sub = ctx.deps.child(target)
        await ctx.deps.emit(EventKind.delegation, f"{caller.value} -> {target.value}: {_clip(request, 400)}",
                            target=target.value, request=request)
        prompt = (f"[Ticket {ctx.deps.ticket_id}] Request from {caller.value}:\n{request}")
        result = await AGENTS[target].run(
            prompt, deps=sub, usage=ctx.usage, event_stream_handler=_log_tool_events,
        )
        report = result.output.model_dump_json()
        await sub.emit(EventKind.delegation_result, f"{target.value} -> {caller.value}: {_clip(result.output.summary, 400)}",
                       report=result.output.model_dump(mode="json"))
        return report

    delegate.__name__ = f"ask_{target.value}"
    return delegate


def _team_context(ctx: RunContext[TeamDeps]) -> str:
    chain = " -> ".join(a.value for a in ctx.deps.chain)
    return (f"Current ticket id: {ctx.deps.ticket_id}. Delegation chain so far: {chain}. "
            f"You are '{ctx.deps.me.value}'. Teammates already in the chain are waiting on you; do not ask them.")


# Full connectivity: every agent can ask every other agent.
for _name, _agent in AGENTS.items():
    _agent.instructions(_team_context)
    for _target in AgentName:
        if _target is not _name:
            _agent.tool(_make_delegate(_target), name=f"ask_{_target.value}",
                        description=DELEGATE_DESCRIPTIONS[_target])


# --------------------------------------------------------------------------- loops

async def run_ticket(ticket_id: int, on_event: EventSink | None = None) -> tuple[BossDecision, TeamDeps]:
    """Boss works one ticket end to end (delegating as needed). Returns the decision and the event log."""
    deps = TeamDeps(ticket_id=ticket_id, chain=(AgentName.boss,), on_event=on_event)
    await deps.emit(EventKind.run_started, f"Boss picks up ticket {ticket_id}")
    try:
        async with CAMPUS_MCP:
            result = await boss_agent.run(
                f"Work ticket {ticket_id} from the board. Start with get_ticket({ticket_id}).",
                deps=deps,
                usage_limits=TICKET_USAGE_LIMITS,
                event_stream_handler=_log_tool_events,
            )
    except Exception as exc:  # surface failures on the feed, then re-raise
        await deps.emit(EventKind.error, f"{type(exc).__name__}: {exc}")
        raise
    await deps.emit(EventKind.run_finished, f"Ticket {ticket_id}: {result.output.final_status.value} - {result.output.decision}",
                    decision=result.output.model_dump(mode="json"), usage=repr(result.usage))
    return result.output, deps


async def run_all_open_tickets(on_event: EventSink | None = None, reset: bool = True) -> list[BossDecision]:
    """Full run: reset the database, then the Boss works every open ticket in board order."""
    if reset:
        reset_database()
    board = await mcp_call("list_open_tickets")
    decisions = []
    for ticket in board["tickets"]:
        decision, _ = await run_ticket(ticket["id"], on_event=on_event)
        decisions.append(decision)
    return decisions
