"""Campus Customs MCP server.

Every agent (Boss, Inventory, Accounting, Facilities, Customer Service) reaches
the shop database only through the tools defined here. All values come straight
from data/campus_customs_new.db; "today" is always desk.date_today, never the
system clock.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

DB_PATH = Path(
    os.environ.get(
        "CAMPUS_DB",
        Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db",
    )
)

mcp = FastMCP("campus-customs")

# Agent-side workflow tables. The original database has nowhere to keep payment
# approvals, purchase orders, message drafts, or ticket history, so they are
# created on demand in the working copy (a reset simply removes them again).
WORKFLOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- 'invoice' | 'rent'
    ref_id INTEGER NOT NULL,         -- invoices.id or leases.id
    ticket_id INTEGER,
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- 'pending' | 'paid' | 'rejected' | 'refused'
    decided_by TEXT,
    decision_note TEXT,
    payment_id INTEGER,
    created_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY,
    vendor_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    total_cost REAL NOT NULL,
    ticket_id INTEGER,
    expected_arrival TEXT NOT NULL,
    status TEXT NOT NULL,            -- 'draft' (stays on the board; never sent to a vendor)
    created_by TEXT NOT NULL,
    created_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    status TEXT NOT NULL,            -- 'draft' (never sent)
    created_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_updates (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    note TEXT NOT NULL,
    author TEXT NOT NULL,
    created_on TEXT NOT NULL
);
"""

TICKET_STATUSES = (
    "open", "in_progress", "waiting_approval", "waiting_vendor",
    "waiting_customer", "resolved", "closed",
)
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(WORKFLOW_SCHEMA)
    return conn


@contextmanager
def _db():
    """Open, commit (or roll back), and always close - so a reset can overwrite the file."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _shop_today(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return date.fromisoformat(row["date_today"])


def check_stock(sku: str, size: str, qty_needed: int = 1) -> dict:
    """Check on-hand stock for one SKU + size against a requested quantity.

    Returns the inventory row (name, qty, location), the shortfall versus
    qty_needed, and the SKU's unit cost / list price / margin from pricing.
    """
    with _db() as conn:
        item = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if item is None:
            sizes = [r["size"] for r in conn.execute("SELECT size FROM inventory WHERE sku = ?", (sku,))]
            return {
                "error": f"No inventory row for sku={sku!r}, size={size!r}.",
                "sizes_on_file_for_sku": sizes,
            }
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()

    in_stock = item["qty"]
    result = {
        "sku": item["sku"],
        "name": item["name"],
        "size": item["size"],
        "location": item["location"],
        "in_stock": in_stock,
        "qty_needed": qty_needed,
        "can_fill_from_stock": in_stock >= qty_needed,
        "shortfall": max(qty_needed - in_stock, 0),
        "pricing": None,
    }
    if price is not None:
        cost, listp = price["unit_cost"], price["list_price"]
        result["pricing"] = {
            "unit_cost": cost,
            "list_price": listp,
            "margin_per_unit": round(listp - cost, 2),
            "margin_pct": round((listp - cost) / listp * 100, 1) if listp else None,
        }
    return result


def check_vendor_restock(vendor_id: int | None = None) -> dict:
    """Show whether each vendor can ship a restock right now.

    For each vendor: specialty, lead_days, any open invoices (with days overdue
    relative to desk.date_today), can_ship (False while any invoice is open),
    and the earliest arrival date (today + lead_days) if it can ship.
    Pass vendor_id to check a single vendor; omit it to list all vendors.
    """
    with _db() as conn:
        today = _shop_today(conn)
        if vendor_id is None:
            vendors = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
        else:
            vendors = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchall()
            if not vendors:
                return {"error": f"No vendor with id={vendor_id}."}
        out = []
        for v in vendors:
            open_invoices = [
                {
                    "invoice_id": inv["id"],
                    "amount": inv["amount"],
                    "due_date": inv["due_date"],
                    "days_overdue": max((today - date.fromisoformat(inv["due_date"])).days, 0),
                    "description": inv["description"],
                }
                for inv in conn.execute(
                    "SELECT * FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
                    (v["id"],),
                )
            ]
            can_ship = not open_invoices
            out.append({
                "vendor_id": v["id"],
                "name": v["name"],
                "specialty": v["specialty"],
                "lead_days": v["lead_days"],
                "open_invoices": open_invoices,
                "can_ship": can_ship,
                "blocked_reason": None if can_ship else "Vendor will not ship while it has an open unpaid invoice.",
                "earliest_arrival_if_ordered_today": (
                    (today + timedelta(days=v["lead_days"])).isoformat() if can_ship else None
                ),
            })
    return {"shop_today": today.isoformat(), "vendors": out}


def list_bills_due() -> dict:
    """List every open bill (vendor invoices + lease rent) against cash on hand.

    Each bill shows amount, due date, and days until due (negative = overdue)
    relative to desk.date_today. Also returns cash balances and whether cash
    covers all open bills. Read-only: this tool never pays anything.
    """
    with _db() as conn:
        today = _shop_today(conn)
        bills = []
        for inv in conn.execute(
            "SELECT i.*, v.name AS vendor_name FROM invoices i "
            "JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open'"
        ):
            bills.append({
                "kind": "invoice",
                "ref_id": inv["id"],
                "payee": inv["vendor_name"],
                "amount": inv["amount"],
                "due_date": inv["due_date"],
                "description": inv["description"],
            })
        for lease in conn.execute("SELECT * FROM leases"):
            bills.append({
                "kind": "rent",
                "ref_id": lease["id"],
                "payee": lease["landlord"],
                "amount": lease["monthly_rent"],
                "due_date": lease["next_due"],
                "description": f"Monthly rent for {lease['space_name']}",
            })
        cash = [dict(r) for r in conn.execute("SELECT name, balance, date FROM cash_accounts")]

    for b in bills:
        days = (date.fromisoformat(b["due_date"]) - today).days
        b["days_until_due"] = days
        b["overdue"] = days < 0
    bills.sort(key=lambda b: b["due_date"])

    total_due = round(sum(b["amount"] for b in bills), 2)
    total_cash = round(sum(c["balance"] for c in cash), 2)
    return {
        "shop_today": today.isoformat(),
        "bills": bills,
        "total_due": total_due,
        "cash_accounts": cash,
        "total_cash": total_cash,
        "cash_covers_all_bills": total_cash >= total_due,
        "cash_left_if_all_paid": round(total_cash - total_due, 2),
    }


def _add_one_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(d)


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur]


# ---------------------------------------------------------------- tickets

def list_tickets() -> dict:
    """List every ticket (any status), oldest first, with shop today and its latest status note."""
    with _db() as conn:
        today = _shop_today(conn)
        tickets = _rows(conn.execute(
            "SELECT t.*, (SELECT note FROM ticket_updates u WHERE u.ticket_id = t.id ORDER BY u.id DESC LIMIT 1) "
            "AS last_note FROM tickets t ORDER BY t.created_at"))
    return {"shop_today": today.isoformat(), "tickets": tickets}


def get_cash_balance(account: str = "checking") -> dict:
    """Current balance of one cash account (default 'checking') from cash_accounts."""
    with _db() as conn:
        row = conn.execute("SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    if row is None:
        return {"error": f"No cash account named {account!r}."}
    return dict(row)


def list_open_tickets() -> dict:
    """List every ticket that is not resolved or closed, oldest first, with shop today."""
    with _db() as conn:
        today = _shop_today(conn)
        tickets = _rows(conn.execute(
            "SELECT * FROM tickets WHERE status NOT IN ('resolved', 'closed') ORDER BY created_at"
        ))
    return {"shop_today": today.isoformat(), "tickets": tickets}


def get_ticket(ticket_id: int) -> dict:
    """Get one ticket plus every database row it links to.

    Resolves: the inventory row and pricing for its sku/size, its invoice and
    that invoice's vendor, its lease, and everything the team has already done
    on it (payment approvals, purchase orders, message drafts, status history).
    """
    with _db() as conn:
        today = _shop_today(conn)
        t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"error": f"No ticket with id={ticket_id}."}
        t = dict(t)
        linked: dict = {}
        if t["sku"]:
            linked["inventory"] = _rows(conn.execute(
                "SELECT * FROM inventory WHERE sku = ? AND size = ?", (t["sku"], t["size"])))
            linked["pricing"] = _rows(conn.execute("SELECT * FROM pricing WHERE sku = ?", (t["sku"],)))
        if t["invoice_id"] is not None:
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (t["invoice_id"],)).fetchone()
            linked["invoice"] = dict(inv) if inv else None
            if inv:
                v = conn.execute("SELECT * FROM vendors WHERE id = ?", (inv["vendor_id"],)).fetchone()
                linked["invoice_vendor"] = dict(v) if v else None
        if t["lease_id"] is not None:
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (t["lease_id"],)).fetchone()
            linked["lease"] = dict(lease) if lease else None
        work = {
            "approvals": _rows(conn.execute("SELECT * FROM approvals WHERE ticket_id = ? ORDER BY id", (ticket_id,))),
            "purchase_orders": _rows(conn.execute("SELECT * FROM purchase_orders WHERE ticket_id = ? ORDER BY id", (ticket_id,))),
            "drafts": _rows(conn.execute("SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))),
            "status_history": _rows(conn.execute("SELECT * FROM ticket_updates WHERE ticket_id = ? ORDER BY id", (ticket_id,))),
        }
    return {"shop_today": today.isoformat(), "ticket": t, "linked": linked, "team_work_so_far": work}


def update_ticket_status(ticket_id: int, status: str, note: str, author: str) -> dict:
    """Move a ticket to a new status and record why in its status history.

    status must be one of: open, in_progress, waiting_approval, waiting_vendor,
    waiting_customer, resolved, closed. note should state the reason in one or
    two sentences. author is the agent making the change (e.g. 'boss').
    """
    if status not in TICKET_STATUSES:
        return {"error": f"Invalid status {status!r}. Use one of {list(TICKET_STATUSES)}."}
    if not note.strip():
        return {"error": "A note explaining the status change is required."}
    with _db() as conn:
        today = _shop_today(conn)
        t = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"error": f"No ticket with id={ticket_id}."}
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        conn.execute(
            "INSERT INTO ticket_updates (ticket_id, old_status, new_status, note, author, created_on) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, t["status"], status, note.strip(), author, today.isoformat()),
        )
    return {"ticket_id": ticket_id, "old_status": t["status"], "new_status": status, "note": note.strip()}


# ---------------------------------------------------------------- facilities / pricing

def get_lease(lease_id: int) -> dict:
    """Get one lease (space, landlord, monthly rent, next due date) with days until rent is due."""
    with _db() as conn:
        today = _shop_today(conn)
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if lease is None:
            return {"error": f"No lease with id={lease_id}."}
        paid = _rows(conn.execute(
            "SELECT * FROM payments WHERE kind = 'rent' AND ref_id = ? ORDER BY id", (lease_id,)))
    days = (date.fromisoformat(lease["next_due"]) - today).days
    return {
        "shop_today": today.isoformat(),
        "lease": dict(lease),
        "days_until_due": days,
        "overdue": days < 0,
        "rent_payments_on_record": paid,
    }


def quote_discount(sku: str, qty: int, discount_pct: float) -> dict:
    """Price a bulk order of qty units of sku at discount_pct off list price.

    Returns list vs. discounted unit price and order total, unit cost, margin
    per unit, margin %, total gross profit, and whether the price falls below
    cost. Uses only the pricing table; it does not change any price.
    """
    if qty <= 0:
        return {"error": "qty must be positive."}
    if not 0 <= discount_pct < 100:
        return {"error": "discount_pct must be between 0 and 100."}
    with _db() as conn:
        p = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
    if p is None:
        return {"error": f"No pricing row for sku={sku!r}."}
    cost, listp = p["unit_cost"], p["list_price"]
    unit = round(listp * (1 - discount_pct / 100), 2)
    return {
        "sku": sku,
        "qty": qty,
        "discount_pct": discount_pct,
        "list_unit_price": listp,
        "discounted_unit_price": unit,
        "list_total": round(listp * qty, 2),
        "discounted_total": round(unit * qty, 2),
        "unit_cost": cost,
        "margin_per_unit": round(unit - cost, 2),
        "margin_pct": round((unit - cost) / unit * 100, 1) if unit else None,
        "total_gross_profit": round((unit - cost) * qty, 2),
        "below_cost": unit < cost,
        "max_discount_pct_before_loss": round((1 - cost / listp) * 100, 1),
    }


# ---------------------------------------------------------------- purchasing

def create_purchase_order(vendor_id: int, sku: str, size: str, qty: int, ticket_id: int, created_by: str) -> dict:
    """Draft a restock purchase order (stays on the board; nothing is sent to the vendor).

    Refuses if the vendor has any open unpaid invoice (vendors will not ship
    until paid), if the sku/size is not in inventory, or if there is no
    pricing row. Cost comes from pricing.unit_cost; expected arrival is
    desk.date_today + vendors.lead_days. No cash moves when a PO is drafted.
    """
    if qty <= 0:
        return {"error": "qty must be positive."}
    with _db() as conn:
        today = _shop_today(conn)
        v = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if v is None:
            return {"error": f"No vendor with id={vendor_id}."}
        blocking = _rows(conn.execute(
            "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open'", (vendor_id,)))
        if blocking:
            return {
                "refused": True,
                "reason": f"{v['name']} will not ship while it has open unpaid invoice(s).",
                "blocking_invoices": blocking,
            }
        if conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone() is None:
            return {"error": f"No inventory row for sku={sku!r}, size={size!r}."}
        p = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if p is None:
            return {"error": f"No pricing row for sku={sku!r}; cannot cost the order."}
        arrival = (today + timedelta(days=v["lead_days"])).isoformat()
        total = round(p["unit_cost"] * qty, 2)
        cur = conn.execute(
            "INSERT INTO purchase_orders (vendor_id, sku, size, qty, unit_cost, total_cost, ticket_id, "
            "expected_arrival, status, created_by, created_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)",
            (vendor_id, sku, size, qty, p["unit_cost"], total, ticket_id, arrival, created_by, today.isoformat()),
        )
    return {
        "purchase_order_id": cur.lastrowid,
        "vendor": v["name"],
        "sku": sku,
        "size": size,
        "qty": qty,
        "unit_cost": p["unit_cost"],
        "total_cost": total,
        "expected_arrival": arrival,
        "status": "draft",
        "note": "Draft only - not sent to the vendor. No cash moved.",
    }


# ---------------------------------------------------------------- payments

def _payable(conn, kind: str, ref_id: int):
    """Look up what is owed for an invoice or a lease. Returns (payee, amount, description) or an error dict."""
    if kind == "invoice":
        inv = conn.execute(
            "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (ref_id,)).fetchone()
        if inv is None:
            return {"error": f"No invoice with id={ref_id}."}
        if inv["status"] != "open":
            return {"error": f"Invoice {ref_id} is '{inv['status']}', not open."}
        return inv["vendor_name"], inv["amount"], inv["description"]
    if kind == "rent":
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
        if lease is None:
            return {"error": f"No lease with id={ref_id}."}
        return lease["landlord"], lease["monthly_rent"], f"Rent for {lease['space_name']} due {lease['next_due']}"
    return {"error": "kind must be 'invoice' or 'rent'."}


def request_payment(kind: str, ref_id: int, ticket_id: int, reason: str, requested_by: str, account: str = "checking") -> dict:
    """Put a payment in the human approval queue. This does NOT move any money.

    kind is 'invoice' (ref_id = invoices.id) or 'rent' (ref_id = leases.id).
    The amount and payee are read from the database, never supplied by the
    agent. Refuses if the bill is not payable, if the same bill already has a
    pending request, or if the account balance is lower than the amount.
    """
    if not reason.strip():
        return {"error": "A reason is required so the human approver knows why."}
    with _db() as conn:
        today = _shop_today(conn)
        found = _payable(conn, kind, ref_id)
        if isinstance(found, dict):
            return found
        payee, amount, desc = found
        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            return {"error": f"No cash account named {account!r}."}
        dup = conn.execute(
            "SELECT id FROM approvals WHERE kind = ? AND ref_id = ? AND status = 'pending'", (kind, ref_id)).fetchone()
        if dup:
            return {"error": f"Approval #{dup['id']} for this {kind} is already pending.", "approval_id": dup["id"]}
        if acct["balance"] < amount:
            return {
                "refused": True,
                "reason": f"Not enough cash: {account} has {acct['balance']:.2f}, payment needs {amount:.2f}.",
            }
        pending_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM approvals WHERE status = 'pending' AND account = ?",
            (account,)).fetchone()["s"]
        cur = conn.execute(
            "INSERT INTO approvals (kind, ref_id, ticket_id, payee, amount, account, reason, requested_by, status, created_on) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (kind, ref_id, ticket_id, payee, amount, account, reason.strip(), requested_by, today.isoformat()),
        )
    after_all = round(acct["balance"] - pending_total - amount, 2)
    return {
        "approval_id": cur.lastrowid,
        "status": "pending",
        "kind": kind,
        "ref_id": ref_id,
        "payee": payee,
        "amount": amount,
        "description": desc,
        "account": account,
        "balance_now": acct["balance"],
        "balance_if_all_pending_paid": after_all,
        "warning": None if after_all >= 0 else "Pending requests together exceed the balance; the human must choose.",
        "note": "Waiting for a human to approve on the dashboard. No money has moved.",
    }


def list_approvals(status: str | None = None) -> dict:
    """List payment approval requests, optionally filtered by status (pending, paid, rejected, refused)."""
    with _db() as conn:
        if status:
            rows = _rows(conn.execute("SELECT * FROM approvals WHERE status = ? ORDER BY id", (status,)))
        else:
            rows = _rows(conn.execute("SELECT * FROM approvals ORDER BY id"))
        cash = _rows(conn.execute("SELECT name, balance FROM cash_accounts"))
    return {"approvals": rows, "cash_accounts": cash}


def approve_and_pay(approval_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Approve a pending payment request and pay it.

    Refuses if approved_by is empty or an agent name, if the request is not
    pending, if the bill changed or was already paid, or if the account does
    not have enough cash (balances never go negative). On success, in one
    transaction: writes a payments row, debits cash_accounts, and marks the
    invoice 'paid' or advances the lease's next_due by one month.
    """
    who = (approved_by or "").strip()
    if not who or who.lower() in AGENT_NAMES:
        return {"refused": True, "reason": "Payments must be approved by a named human, not an agent."}
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        today = _shop_today(conn)
        a = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if a is None:
            conn.rollback()
            return {"error": f"No approval with id={approval_id}."}
        if a["status"] != "pending":
            conn.rollback()
            return {"refused": True, "reason": f"Approval #{approval_id} is '{a['status']}', not pending."}
        found = _payable(conn, a["kind"], a["ref_id"])
        if isinstance(found, dict):
            conn.rollback()
            return {"refused": True, "reason": found["error"]}
        _, amount, _ = found
        if amount != a["amount"]:
            conn.rollback()
            return {"refused": True, "reason": f"Bill amount changed from {a['amount']} to {amount}; request again."}
        bal = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (a["account"],)).fetchone()
        if bal is None or bal["balance"] < amount:
            have = bal["balance"] if bal else 0
            conn.execute(
                "UPDATE approvals SET status = 'refused', decided_by = ?, decision_note = ? WHERE id = ?",
                (who, f"Insufficient cash: {have:.2f} < {amount:.2f}", approval_id))
            conn.commit()
            return {"refused": True, "reason": f"Not enough cash in {a['account']}: {have:.2f} < {amount:.2f}. Nothing was paid."}
        new_balance = round(bal["balance"] - amount, 2)
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                     (new_balance, today.isoformat(), a["account"]))
        pay = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (a["kind"], a["ref_id"], amount, a["account"], today.isoformat(), who))
        if a["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (a["ref_id"],))
            effect = f"Invoice {a['ref_id']} marked paid."
        else:
            lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (a["ref_id"],)).fetchone()
            nxt = _add_one_month(date.fromisoformat(lease["next_due"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (nxt, a["ref_id"]))
            effect = f"Lease {a['ref_id']} next_due moved {lease['next_due']} -> {nxt}."
        conn.execute(
            "UPDATE approvals SET status = 'paid', decided_by = ?, payment_id = ? WHERE id = ?",
            (who, pay.lastrowid, approval_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "paid": True,
        "approval_id": approval_id,
        "ticket_id": a["ticket_id"],
        "payment_id": pay.lastrowid,
        "amount": amount,
        "account": a["account"],
        "balance_after": new_balance,
        "approved_by": who,
        "effect": effect,
    }


def reject_payment(approval_id: int, rejected_by: str, note: str = "") -> dict:
    """HUMAN ONLY. Reject a pending payment request. No money moves."""
    who = (rejected_by or "").strip()
    if not who or who.lower() in AGENT_NAMES:
        return {"refused": True, "reason": "Only a named human can reject a payment request."}
    with _db() as conn:
        a = conn.execute("SELECT status, ticket_id FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if a is None:
            return {"error": f"No approval with id={approval_id}."}
        if a["status"] != "pending":
            return {"refused": True, "reason": f"Approval #{approval_id} is '{a['status']}', not pending."}
        conn.execute("UPDATE approvals SET status = 'rejected', decided_by = ?, decision_note = ? WHERE id = ?",
                     (who, note, approval_id))
    return {"approval_id": approval_id, "ticket_id": a["ticket_id"], "status": "rejected", "rejected_by": who}


def list_purchase_orders(status: str | None = None) -> dict:
    """List purchase orders, optionally filtered by status ('draft' or 'approved'), with vendor names."""
    sql = ("SELECT p.*, v.name AS vendor_name FROM purchase_orders p JOIN vendors v ON v.id = p.vendor_id"
           + (" WHERE p.status = ?" if status else "") + " ORDER BY p.id")
    with _db() as conn:
        rows = _rows(conn.execute(sql, (status,) if status else ()))
    return {"purchase_orders": rows}


def approve_purchase_order(po_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Approve a draft purchase order. Moves no cash and sends nothing to the vendor.

    Re-checks that the vendor still has no open invoice before approving.
    """
    who = (approved_by or "").strip()
    if not who or who.lower() in AGENT_NAMES:
        return {"refused": True, "reason": "Purchase orders must be approved by a named human, not an agent."}
    with _db() as conn:
        po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
        if po is None:
            return {"error": f"No purchase order with id={po_id}."}
        if po["status"] != "draft":
            return {"refused": True, "reason": f"PO #{po_id} is '{po['status']}', not draft."}
        blocking = _rows(conn.execute(
            "SELECT id, amount FROM invoices WHERE vendor_id = ? AND status = 'open'", (po["vendor_id"],)))
        if blocking:
            return {"refused": True, "reason": "Vendor has an open unpaid invoice; it will not ship.",
                    "blocking_invoices": blocking}
        conn.execute("UPDATE purchase_orders SET status = 'approved' WHERE id = ?", (po_id,))
    return {"purchase_order_id": po_id, "status": "approved", "approved_by": who,
            "note": "Approved on the board. Not sent to the vendor; no cash moved."}


# ---------------------------------------------------------------- customer service

def save_draft_message(ticket_id: int, recipient: str, subject: str, body: str, author: str) -> dict:
    """Save a message draft to the board. It is NEVER sent - a human reviews it.

    Use for customer replies (and any vendor/landlord note). recipient must be
    the person or organization on the ticket.
    """
    if not body.strip():
        return {"error": "Draft body is empty."}
    with _db() as conn:
        today = _shop_today(conn)
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"No ticket with id={ticket_id}."}
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, recipient, subject, body, author, status, created_on) "
            "VALUES (?, ?, ?, ?, ?, 'draft', ?)",
            (ticket_id, recipient, subject, body.strip(), author, today.isoformat()),
        )
    return {"draft_id": cur.lastrowid, "ticket_id": ticket_id, "recipient": recipient,
            "status": "draft", "note": "Saved to the board only. Not sent."}


AGENT_TOOLS = (
    check_stock, check_vendor_restock, list_bills_due,
    list_open_tickets, get_ticket, update_ticket_status,
    get_lease, quote_discount, create_purchase_order,
    request_payment, list_approvals, save_draft_message,
    list_tickets, get_cash_balance, list_purchase_orders,
)
HUMAN_ONLY_TOOLS = (approve_and_pay, reject_payment, approve_purchase_order)

for _tool in AGENT_TOOLS + HUMAN_ONLY_TOOLS:
    mcp.tool(_tool)


if __name__ == "__main__":
    mcp.run()
