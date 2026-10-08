"""FastAPI backend for the Campus Customs dashboard.

Start it from the backend/ folder:

    uvicorn main:app --reload --port 8000

Every read and write goes through the campus-customs MCP server. Agents only
*prepare* payments; the /approve route (a human click) is the only thing that
moves cash.
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# Let `uvicorn main:app` (run from backend/) import the `backend` package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.models import AgentEvent  # noqa: E402
from backend.shared import BACKEND_MCP, MODEL_NAME, mcp_call, portkey_key, reset_database  # noqa: E402
from backend.team import run_ticket  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with BACKEND_MCP:  # one MCP session for all route calls while the server is up
        yield


app = FastAPI(title="Campus Customs backend", version="1.0", lifespan=lifespan)

# The React dashboard is served by Vite on its own port; let the browser call us from there.
FRONTEND_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",   # vite dev
    "http://localhost:4173", "http://127.0.0.1:4173",   # vite preview
]
app.add_middleware(
    CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"],
)

# A ticket counts as resolved once the team's run has finished: the Boss always
# ends a run by moving the ticket out of open/in_progress. `status` still says
# what (if anything) it is waiting on, e.g. waiting_approval.
UNWORKED_STATUSES = {"open", "in_progress"}


# --------------------------------------------------------------------------- in-memory board state

class Board:
    """Activity feed + which ticket the team is working on. One run at a time (cash is shared)."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.running_ticket: int | None = None
        self.task: asyncio.Task | None = None
        self.decisions: dict[int, dict] = {}
        self.errors: dict[int, str] = {}

    def add(self, event: dict[str, Any]) -> None:
        self.events.append({"id": len(self.events) + 1, **event})

    async def on_agent_event(self, event: AgentEvent) -> None:
        self.add(event.model_dump(mode="json"))

    def human(self, kind: str, detail: str, ticket_id: int | None = None, **data: Any) -> None:
        self.add({"at": datetime.now().isoformat(), "ticket_id": ticket_id, "agent": "human",
                  "kind": kind, "detail": detail, "data": data})


board = Board()


# --------------------------------------------------------------------------- audit trail

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"


def append_audit(entry: dict[str, Any]) -> None:
    """Append one record (agent run, human decision, reset) to output/audit_trail.json."""
    try:
        trail = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        trail = {"description": "Append-only log of real Campus Customs runs: every agent run on a ticket "
                                "(with its full event stream), every human payment/PO decision, and every reset.",
                 "entries": []}
    entry = {"seq": len(trail["entries"]) + 1, "recorded_at": datetime.now().isoformat(timespec="seconds"), **entry}
    trail["entries"].append(entry)
    AUDIT_PATH.parent.mkdir(exist_ok=True)
    tmp = AUDIT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(trail, indent=2, default=str), encoding="utf-8")
    tmp.replace(AUDIT_PATH)


async def _checking_balance() -> float:
    return (await mcp_call("get_cash_balance", account="checking"))["balance"]


def _check(result: dict) -> dict:
    """Turn MCP tool errors/refusals into HTTP errors."""
    if isinstance(result, dict):
        if result.get("refused"):
            raise HTTPException(409, detail=result)
        if "error" in result:
            status = 404 if "No " in result["error"] else 400
            raise HTTPException(status, detail=result["error"])
    return result


# --------------------------------------------------------------------------- tickets

@app.get("/tickets")
async def list_tickets():
    """All tickets with a board state: open (not worked yet), running, or resolved (team run finished)."""
    data = await mcp_call("list_tickets")
    return {
        "shop_today": data["shop_today"],
        "running_ticket": board.running_ticket,
        "tickets": [
            {
                **t,
                "state": ("running" if board.running_ticket == t["id"]
                          else "open" if t["status"] in UNWORKED_STATUSES else "resolved"),
                "running": board.running_ticket == t["id"],
                "last_decision": board.decisions.get(t["id"]),
                "last_error": board.errors.get(t["id"]),
            }
            for t in data["tickets"]
        ],
    }


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    """One ticket with linked rows and the team's work on it (approvals, POs, drafts, history)."""
    data = _check(await mcp_call("get_ticket", ticket_id=ticket_id))
    data["last_decision"] = board.decisions.get(ticket_id)
    return data


async def _run(ticket_id: int) -> None:
    first_event = len(board.events)
    started, t0 = datetime.now().isoformat(timespec="seconds"), time.monotonic()
    cash_before = await _checking_balance()
    record: dict[str, Any] = {"type": "agent_run", "ticket_id": ticket_id, "model": MODEL_NAME, "started_at": started}
    try:
        decision, _ = await run_ticket(ticket_id, on_event=board.on_agent_event)
        board.decisions[ticket_id] = decision.model_dump(mode="json")
        board.errors.pop(ticket_id, None)
        record["outcome"] = "finished"
        record["decision"] = board.decisions[ticket_id]
    except Exception as exc:  # already on the feed via run_ticket; keep it for /tickets too
        board.errors[ticket_id] = f"{type(exc).__name__}: {exc}"
        record["outcome"] = "failed"
        record["error"] = board.errors[ticket_id]
    finally:
        board.running_ticket = None
        board.task = None
        record["seconds"] = round(time.monotonic() - t0, 1)
        record["checking_before"] = cash_before
        record["checking_after"] = await _checking_balance()
        record["events"] = [e for e in board.events[first_event:] if e["ticket_id"] == ticket_id]
        append_audit(record)


@app.post("/tickets/{ticket_id}/run")
async def run_team(ticket_id: int, wait: bool = Query(False, description="Block until the Boss finishes.")):
    """Run the agent team on one ticket. Returns immediately; watch /events. Use ?wait=true to block."""
    if not portkey_key():
        raise HTTPException(503, detail="PORTKEY_API_KEY is not set (add it to the .env file at the project root); the agents can't run.")
    if board.running_ticket is not None:
        raise HTTPException(409, detail=f"The team is already working on ticket {board.running_ticket}.")
    _check(await mcp_call("get_ticket", ticket_id=ticket_id))  # 404 if no such ticket

    board.running_ticket = ticket_id
    board.task = asyncio.create_task(_run(ticket_id))
    if wait:
        await board.task
        if ticket_id in board.errors:
            raise HTTPException(500, detail=board.errors[ticket_id])
        return {"ticket_id": ticket_id, "status": "finished", "decision": board.decisions[ticket_id]}
    return {"ticket_id": ticket_id, "status": "started"}


# --------------------------------------------------------------------------- events

@app.get("/events")
async def get_events(
    since: int = Query(0, description="Only events with id greater than this (poll with the last id you saw)."),
    ticket_id: int | None = Query(None),
    limit: int = Query(200, le=1000),
):
    """Recent agent events: delegations (what each agent asked and answered) and MCP tool calls/results."""
    events = [e for e in board.events if e["id"] > since and (ticket_id is None or e["ticket_id"] == ticket_id)]
    return {"running_ticket": board.running_ticket, "last_id": len(board.events), "events": events[-limit:]}


# --------------------------------------------------------------------------- approvals (human)

@app.get("/approvals")
async def list_approvals(status: str | None = Query("pending")):
    """Payment requests and purchase orders waiting for (or past) a human decision."""
    pays = await mcp_call("list_approvals", status=status)
    po_status = {"pending": "draft"}.get(status, status)
    pos = await mcp_call("list_purchase_orders", status=po_status)
    return {"payments": pays["approvals"], "purchase_orders": pos["purchase_orders"], "cash_accounts": pays["cash_accounts"]}


class ApproveRequest(BaseModel):
    kind: Literal["payment", "purchase_order"] = "payment"
    id: int = Field(description="Approval id (payment) or purchase order id.")
    approved_by: str = Field(min_length=1, description="Name of the human clicking approve.")


@app.post("/approve")
async def approve(req: ApproveRequest):
    """Human approves. For a payment this is the only route that moves cash; it refuses if cash is short."""
    if req.kind == "payment":
        result = _check(await mcp_call("approve_and_pay", approval_id=req.id, approved_by=req.approved_by))
        append_audit({"type": "human_decision", "action": "approve_payment", "approval_id": req.id,
                      "approved_by": req.approved_by, "result": result})
        board.human("payment_approved", f"{req.approved_by} approved payment #{req.id}: ${result['amount']:,.2f} "
                    f"({result['effect']}) balance now ${result['balance_after']:,.2f}",
                    ticket_id=result.get("ticket_id"), **{k: v for k, v in result.items() if k != "ticket_id"})
    else:
        result = _check(await mcp_call("approve_purchase_order", po_id=req.id, approved_by=req.approved_by))
        append_audit({"type": "human_decision", "action": "approve_purchase_order", "purchase_order_id": req.id,
                      "approved_by": req.approved_by, "result": result})
        board.human("purchase_order_approved", f"{req.approved_by} approved PO #{req.id}", **result)
    return result


class RejectRequest(BaseModel):
    id: int
    rejected_by: str = Field(min_length=1)
    note: str = ""


@app.post("/reject")
async def reject(req: RejectRequest):
    """Human rejects a pending payment request. No money moves."""
    result = _check(await mcp_call("reject_payment", approval_id=req.id, rejected_by=req.rejected_by, note=req.note))
    append_audit({"type": "human_decision", "action": "reject_payment", "approval_id": req.id,
                  "rejected_by": req.rejected_by, "result": result})
    board.human("payment_rejected", f"{req.rejected_by} rejected payment #{req.id}",
                ticket_id=result.get("ticket_id"), **{k: v for k, v in result.items() if k != "ticket_id"})
    return result


# --------------------------------------------------------------------------- cash / reset

@app.get("/cash")
async def cash():
    """Current checking balance from cash_accounts."""
    return _check(await mcp_call("get_cash_balance", account="checking"))


@app.post("/reset")
async def reset():
    """Copy the original database over the working copy and clear the activity feed."""
    if board.running_ticket is not None:
        raise HTTPException(409, detail=f"Can't reset while the team is working on ticket {board.running_ticket}.")
    reset_database()
    board.events.clear()
    board.decisions.clear()
    board.errors.clear()
    balance = await mcp_call("get_cash_balance", account="checking")
    append_audit({"type": "reset", "checking_balance": balance["balance"]})
    return {"reset": True, "checking_balance": balance["balance"]}


@app.get("/")
async def root():
    return {"service": "Campus Customs backend", "docs": "/docs",
            "routes": ["/tickets", "/tickets/{id}", "/tickets/{id}/run", "/events", "/approvals",
                       "/approve", "/reject", "/cash", "/reset"]}
