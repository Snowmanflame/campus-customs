# Campus Customs: a multi-agent shop desk

A five-agent team runs a campus merch shop. Tickets land on a board (customer orders, rent notices, unpaid bills, discount requests), and the agents resolve them while a human watches and approves payments.

Three pieces talk to each other:

1. **MCP server** (`mcp_server/`, FastMCP): the only way anyone touches the shop database. It has 18 tools, 3 of them human-only.
2. **FastAPI backend with a multi-agent team** (`backend/`, Pydantic AI): Boss, Inventory, Accounting, Facilities and Customer Service.
3. **React dashboard** (`frontend/`, React + Vite + TypeScript): watch the agents work, approve payments, and see cash move.

All agents run on **gpt-6-luna** through the **Portkey** AI gateway.

## Repository layout

| Path | What it is |
|---|---|
| `data/campus_customs.db` | **Original** database. Never modified. |
| `data/campus_customs_new.db` | **Working copy** the agents read and write. Committed as it stands after the graded run (checking $160.00). |
| `mcp_server/server.py` | MCP server (tools, business rules, payment safety) |
| `.mcp.json` | MCP connection config (server `campus-customs`, stdio) |
| `backend/` | Agents (`boss.py`, `inventory.py`, `accounting.py`, `facilities.py`, `customer_service.py`), prompts (`prompts/`), types (`models.py`), team wiring (`team.py`), API (`main.py`) |
| `frontend/` | React dashboard |
| `output/` | Deliverables: `harness.md`, `desk_tickets.html` (plan vs. actual + cash ledger), `resolved_tickets.json`, `resolved_board.html` (screenshots), `audit_trail.json`, `design.md`, `mcp_smoke.json` |
| `AI_prompts.md` | Log of every prompt given to the AI coding assistant |

## Setup (once)

You need **Python 3.11+**, **Node 20+**, and a **Portkey API key** that can reach `gpt-6-luna`.

```bash
git clone <this repo> campus-customs
cd campus-customs

# Python environment (Windows: .venv\Scripts\activate)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Dashboard dependencies
cd frontend && npm install && cd ..

# Your secret key: copy the template and fill it in
cp .env.example .env
# then edit .env:  PORTKEY_API_KEY=...
```

`.env` is git-ignored. Never commit it.

## 1. Copy the original DB to the working copy (clean run)

The agents only ever change `data/campus_customs_new.db`. When you want a clean slate, copy the original over it:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

On Windows PowerShell, use `Copy-Item data\campus_customs.db data\campus_customs_new.db -Force`. Once the backend is running, the dashboard's **NEW GAME · RESET DB** button and `POST /reset` do the same thing.

## 2. Start the MCP server

The backend starts the MCP server for you, over stdio, from `.mcp.json`. You don't need a separate terminal for normal use. To run it on its own, for example to inspect the tools:

```bash
python mcp_server/server.py
```

To call the tools from Claude Code, open this folder in Claude Code (with the virtual environment active). It picks up `.mcp.json` and offers the `campus-customs` server. To check every core tool against the database:

```bash
python mcp_server/smoke_test.py
```

## 3. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

This serves http://localhost:8000, with interactive API docs at http://localhost:8000/docs.

| Route | What it does |
|---|---|
| `GET /tickets` | All tickets, each open / running / resolved |
| `GET /tickets/{id}` | One ticket with approvals, POs, drafts, history |
| `POST /tickets/{id}/run` | Run the agent team on a ticket (`?wait=true` to block) |
| `GET /events?since=N` | What each agent said and which tools it used |
| `GET /approvals` | Payments and purchase orders waiting for a human |
| `POST /approve` | Human approves a payment (the only thing that moves cash) or a PO |
| `POST /reject` | Human rejects a payment request |
| `GET /cash` | Checking balance from `cash_accounts` |
| `POST /reset` | Copy the original DB over the working copy |

## 4. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

This opens http://localhost:5173. The board talks to the backend at `http://localhost:8000` (set in `frontend/.env`), and the backend only accepts browser calls from the Vite origin.

## 5. Reset the DB, then run all three tickets

Always start a full run from a clean database:

1. Press **NEW GAME · RESET DB** on the board, or run `curl -X POST localhost:8000/reset`. Checking should read **$3,400.00**.
2. Select a ticket lane and press **LAUNCH TEAM**. Do 101, 103 and 102 in turn.
3. When agents queue a payment, type your name in **OPERATOR** and press **APPROVE & PAY** (or **REJECT**). Agents can only *request* payments.
4. Launch each ticket again so the team can finish the steps that waited on payment, such as drafting the restock PO or closing the rent ticket.

From the command line:

```bash
curl -X POST localhost:8000/reset
```
```bash
curl -X POST "localhost:8000/tickets/101/run?wait=true"
```

## Business rules (enforced in code)

- **Today:** `desk.date_today` (2026-08-31) is "today" for every overdue and due-date calculation.
- **Lead times** come from `vendors.lead_days`.
- **Blocked vendors:** a vendor with an open unpaid invoice won't ship, and purchase orders to it are refused.
- **Payments:** only payments need human approval, and every payment does. Agents can only queue them.
- **Cash safety:** the pay tool refuses if cash is short. The balance never goes negative, and cash only goes out.
- **Bookkeeping:** a payment writes `payments`, debits `cash_accounts`, and marks the invoice paid or moves the lease's next due date forward, all in one transaction.
- **No outside contact:** customer messages and purchase orders are drafts on the board. Nothing is sent to customers or vendors.
- **Audit trail:** every run, approval and reset is appended to `output/audit_trail.json`.

More detail is in `output/harness.md`.
