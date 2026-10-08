"""Data types shared by the Campus Customs agent team.

Run-time state (TeamDeps, AgentEvent) plus the structured report each agent
must return. Every number in a report must come from an MCP tool result.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    boss = "boss"
    inventory = "inventory"
    accounting = "accounting"
    facilities = "facilities"
    customer_service = "customer_service"


class TicketStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    waiting_approval = "waiting_approval"   # a payment is in the human approval queue
    waiting_vendor = "waiting_vendor"       # restock PO drafted, goods not here yet
    waiting_customer = "waiting_customer"   # reply drafted, customer must decide
    resolved = "resolved"
    closed = "closed"


# --------------------------------------------------------------------------- run-time state

class EventKind(str, Enum):
    run_started = "run_started"
    delegation = "delegation"           # one agent asks another
    delegation_result = "delegation_result"
    delegation_refused = "delegation_refused"
    tool_call = "tool_call"             # agent calls an MCP tool
    tool_result = "tool_result"
    run_finished = "run_finished"
    error = "error"


class AgentEvent(BaseModel):
    """One line on the board's activity feed."""
    at: datetime = Field(default_factory=datetime.now)
    ticket_id: int | None
    agent: AgentName
    kind: EventKind
    detail: str
    data: dict[str, Any] = Field(default_factory=dict)


EventSink = Callable[[AgentEvent], Awaitable[None] | None]


@dataclass
class TeamDeps:
    """Passed to every agent run. `chain` is who is working, outermost first."""
    ticket_id: int | None
    chain: tuple[AgentName, ...]
    events: list[AgentEvent] = field(default_factory=list)
    on_event: EventSink | None = None

    @property
    def me(self) -> AgentName:
        return self.chain[-1]

    def child(self, agent: AgentName) -> "TeamDeps":
        """Deps for a delegated run: same ticket, same event log, one level deeper."""
        return replace(self, chain=self.chain + (agent,))

    async def emit(self, kind: EventKind, detail: str, agent: AgentName | None = None, **data: Any) -> AgentEvent:
        event = AgentEvent(ticket_id=self.ticket_id, agent=agent or self.me, kind=kind, detail=detail, data=data)
        self.events.append(event)
        if self.on_event is not None:
            maybe = self.on_event(event)
            if inspect.isawaitable(maybe):
                await maybe
        return event


# --------------------------------------------------------------------------- agent reports

class SpecialistReport(BaseModel):
    """Fields every specialist report carries."""
    ticket_id: int | None = Field(description="Ticket this work was for.")
    summary: str = Field(description="2-4 sentences: what you checked, what you found, what you did.")
    facts_from_tools: list[str] = Field(
        default_factory=list,
        description="Each key number/date you relied on, with the tool it came from, e.g. 'check_stock: CC-TEE-WHITE S qty 0'.")
    blockers: list[str] = Field(default_factory=list, description="Anything stopping the ticket from moving forward.")
    questions_for_boss: list[str] = Field(default_factory=list, description="Decisions only the Boss should make.")


class InventoryReport(SpecialistReport):
    sku: str | None = None
    size: str | None = None
    qty_requested: int | None = None
    in_stock: int | None = None
    shortfall: int | None = None
    restock_vendor_id: int | None = Field(None, description="Vendor whose specialty matches the item.")
    restock_vendor_name: str | None = None
    vendor_can_ship: bool | None = None
    blocking_invoice_ids: list[int] = Field(default_factory=list)
    lead_days: int | None = None
    earliest_arrival: str | None = Field(None, description="desk.date_today + lead_days, only if the vendor can ship now.")
    purchase_order_id: int | None = Field(None, description="Draft PO id if one was created.")


class MarginCheck(BaseModel):
    sku: str
    qty: int
    unit_cost: float
    list_price: float
    proposed_discount_pct: float
    discounted_unit_price: float
    margin_pct: float
    total_gross_profit: float
    max_discount_pct_before_loss: float


class AccountingReport(SpecialistReport):
    cash_balance: float | None = None
    bills_reviewed: list[str] = Field(default_factory=list, description="e.g. 'invoice 501 $840 due 2026-08-28 (3 days overdue)'.")
    payment_approval_ids: list[int] = Field(default_factory=list, description="Approval requests you created (pending human).")
    cash_after_pending: float | None = Field(None, description="Balance if every pending approval is paid.")
    margin_check: MarginCheck | None = None
    recommendation: str | None = Field(None, description="Your recommendation to the Boss, one or two sentences.")


class FacilitiesReport(SpecialistReport):
    lease_id: int | None = None
    space_name: str | None = None
    landlord: str | None = None
    rent_amount: float | None = None
    rent_due: str | None = None
    days_until_due: int | None = None
    overdue: bool | None = None
    payment_approval_id: int | None = None


class CustomerMessageReport(SpecialistReport):
    draft_id: int | None = Field(None, description="Id returned by save_draft_message.")
    recipient: str | None = None
    subject: str | None = None
    body: str | None = None


class BossDecision(BaseModel):
    """The Boss's final call on one ticket."""
    ticket_id: int
    ticket_type: str
    assigned_to: list[AgentName] = Field(description="Specialists who worked the ticket, in order.")
    findings: list[str] = Field(description="Key facts the team established, each traceable to a tool result.")
    actions_taken: list[str] = Field(description="Concrete things done: approvals requested, POs drafted, drafts saved, status changes.")
    pending_human_approvals: list[int] = Field(default_factory=list, description="Approval ids waiting on a human.")
    draft_ids: list[int] = Field(default_factory=list, description="Message drafts saved to the board.")
    purchase_order_ids: list[int] = Field(default_factory=list)
    final_status: TicketStatus
    decision: str = Field(description="The final call in one or two sentences.")
    next_step: str = Field(description="What has to happen next and who does it (human or agent).")
