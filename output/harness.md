# Campus Customs — Harness Notes

Source: `data/campus_customs.db` (pristine original). Agents work on `data/campus_customs_new.db`, which is reset from the original before every full run.

**Contents:** [Tables](#tables) · [MCP tools](#all-mcp-tools-mcp_serverserverpy) · [Five agents](#agent-team-problem-5) · [API routes](#backend-routes-problem-7) · [Dashboard](#dashboard-problem-8) · [Safety rules](#safety-rules) · [Full run results](#full-run-results-problem-9)

| Piece | Where | Run it |
|---|---|---|
| Database (original / working) | `data/campus_customs.db` / `data/campus_customs_new.db` | `POST /reset` copies original → working |
| MCP server (FastMCP, 18 tools) | `mcp_server/server.py`, registered in `.mcp.json` | started automatically over stdio by the backend and agents |
| Agent team (Pydantic AI, 5 agents) | `backend/boss.py` … `customer_service.py`, prompts in `backend/prompts/`, types in `backend/models.py`, wiring in `backend/team.py` | `POST /tickets/{id}/run` |
| Backend (FastAPI) | `backend/main.py` | `cd backend && uvicorn main:app --reload --port 8000` |
| Dashboard (React + Vite + TS) | `frontend/` | `cd frontend && npm run dev` → http://localhost:5173 |

## Tables

### `desk`
Fields: `date_today` (TEXT), `notes` (TEXT)
Why it matters: `date_today` (2026-08-31) is "today" for the shop — every overdue / due-soon / ETA calculation uses it, never the system clock.

### `inventory`
Fields: `sku` (TEXT), `name` (TEXT), `size` (TEXT), `qty` (INTEGER), `location` (TEXT) — PK (`sku`, `size`)
Why it matters: Inventory agent checks stock by SKU + size here to spot shortfalls against ticket quantities.

### `pricing`
Fields: `sku` (TEXT, PK), `unit_cost` (REAL), `list_price` (REAL)
Why it matters: Accounting uses cost vs. list price to check margins on discount requests and to cost out restock purchase orders.

### `vendors`
Fields: `id` (INTEGER, PK), `name` (TEXT), `specialty` (TEXT), `lead_days` (INTEGER)
Why it matters: Inventory picks a restock vendor by `specialty` and gets the lead time from `lead_days` (QuickShip CT is a courier, not a supplier).

### `leases`
Fields: `id` (INTEGER, PK), `space_name` (TEXT), `landlord` (TEXT), `monthly_rent` (REAL), `next_due` (TEXT), `notes` (TEXT)
Why it matters: Facilities reads rent amount and due date here; `next_due` advances after rent is paid.

### `cash_accounts`
Fields: `name` (TEXT, PK), `balance` (REAL), `date` (TEXT)
Why it matters: The pay tool checks and debits `balance` here — it must refuse any payment that would go negative.

### `payments`
Fields: `id` (INTEGER, PK), `kind` (TEXT), `ref_id` (INTEGER), `amount` (REAL), `account` (TEXT), `paid_at` (TEXT), `approved_by` (TEXT)
Why it matters: Ledger of human-approved payments; every payment writes a row here (with `approved_by`) — empty at start.

### `invoices`
Fields: `id` (INTEGER, PK), `vendor_id` (INTEGER → `vendors.id`), `amount` (REAL), `due_date` (TEXT), `status` (TEXT), `description` (TEXT)
Why it matters: An `open` invoice blocks that vendor from shipping; Accounting flags overdue ones (`due_date` < `desk.date_today`) and marks them paid.

### `tickets`
Fields: `id` (INTEGER, PK), `type` (TEXT), `requester` (TEXT), `subject` (TEXT), `sku` (TEXT), `size` (TEXT), `qty` (INTEGER), `lease_id` (INTEGER → `leases.id`), `invoice_id` (INTEGER → `invoices.id`), `status` (TEXT), `notes` (TEXT), `created_at` (TEXT)
Why it matters: The work queue — the Boss reads each ticket and routes it; `sku`/`size`/`lease_id`/`invoice_id` link it to the other tables.

> Note: `PRAGMA foreign_keys` is off, so tools must validate links themselves.

## Open tickets and how they link

| Ticket | Type | Requester | Links to | Key facts (as of 2026-08-31) |
|---|---|---|---|---|
| 101 | `customer_order` | Tauhid Zaman | `inventory` + `pricing` (CC-TEE-WHITE / S), `invoices` 501 → `vendors` 1 | Wants 1 tee, size S; stock **0**. Invoice 501 (Bulldog Print Co, $840, due 2026-08-28) is **open and overdue** → Bulldog won't ship. Lead time 5 days. |
| 102 | `rent_notice` | Elm City Properties | `leases` 1 | Chapel Street shop rent $2,400, due 2026-09-02 (2 days out, not overdue). |
| 103 | `price_override` | Yale AI Club | `inventory` + `pricing` (CC-HOOD-NAVY / M) | Wants 20 hoodies size M + bulk discount; stock **8** → short 12. Cost $22 / list $58. Apparel restock vendor is Bulldog Print → also blocked by invoice 501. |

### Link diagram

```
tickets.101 ──sku,size──> inventory (CC-TEE-WHITE, S: qty 0) ──sku──> pricing
     └──invoice_id──> invoices.501 ──vendor_id──> vendors.1 Bulldog Print Co (lead 5d)

tickets.102 ──lease_id──> leases.1 Chapel Street shop ($2,400 due 2026-09-02)

tickets.103 ──sku,size──> inventory (CC-HOOD-NAVY, M: qty 8) ──sku──> pricing
     (no direct FK; restock by specialty "apparel" → vendors.1, blocked by invoices.501)

payments  ← written on approved pay  → debits cash_accounts.checking ($3,400)
```

### Cross-ticket observations
- Invoice 501 is the shared blocker for tickets 101 and 103.
- Cash: $3,400 covers invoice 501 + rent ($3,240) with $160 left — not enough to also cover restock cost for 12 hoodies + 1 tee ($272 at unit cost).
- Only payments need human approval; everything else (routing, stock checks, drafts) the agents do on their own.

## MCP tools (`mcp_server/server.py`)

All tools run against `data/campus_customs_new.db` and use `desk.date_today` as today. Every agent uses these tools — none touch the database directly.

### 1. `check_stock(sku, size, qty_needed=1)`
**Reads:** `inventory` (the row for that exact SKU + size: `qty`, `location`) and `pricing` (`unit_cost`, `list_price` for that SKU).
**Unlocks:** 101, 103

| Ticket | Call | What it returns | Why it's the right tool |
|---|---|---|---|
| 101 | `check_stock("CC-TEE-WHITE", "S", 1)` | 0 in stock in Aisle B → shortfall 1 | Tauhid's order is a single tee in size S, and this is the one call that confirms the S row is empty so the order can't ship from the shelf and needs a restock. |
| 103 | `check_stock("CC-HOOD-NAVY", "M", 20)` | 8 in stock in Aisle A → shortfall 12; cost $22, list $58, margin 62.1% | The Yale AI Club's request is both a quantity problem (20 size-M hoodies vs. 8 on hand) and a discount problem, and this tool returns the shortfall and the cost/list margin Accounting needs to judge the discount in one call. |

### 2. `check_vendor_restock(vendor_id=None)`
**Reads:** `vendors` (`name`, `specialty`, `lead_days`), `invoices` (open invoices per vendor: `amount`, `due_date`, `status`, `description`), `desk` (`date_today` to compute days overdue and arrival date).
**Unlocks:** 101, 103

| Ticket | Call | What it returns | Why it's the right tool |
|---|---|---|---|
| 101 | `check_vendor_restock(1)` | Bulldog Print Co ("apparel reprint", 5 days) → `can_ship: false`, blocked by invoice 501 ($840, 3 days overdue) | Ticket 101 is linked to invoice 501, and this tool shows that the overdue invoice stops Bulldog from reprinting the size-S tee, which is the real blocker on Tauhid's order. |
| 103 | `check_vendor_restock()` | All 3 vendors; only Bulldog Print's specialty is apparel, and it's blocked; Elm City Gifts (mugs) and QuickShip CT (courier) can ship but don't make hoodies | The 12 missing size-M hoodies can only come from the apparel vendor, and this tool shows that vendor is blocked by the same invoice 501, so the Yale AI Club can't be promised a delivery date until it's paid. |

### 3. `list_bills_due()`
**Reads:** `invoices` + `vendors` (open invoice 501 and payee name), `leases` (`monthly_rent`, `next_due`, `landlord`, `space_name`), `cash_accounts` (`balance`), `desk` (`date_today`).
**Unlocks:** 102, 101

| Ticket | What it returns | Why it's the right tool |
|---|---|---|
| 102 | Rent to Elm City Properties, $2,400, due 2026-09-02 → `days_until_due: 2`, not overdue | Elm City Properties' notice says rent is due in 2 days, and this tool checks that claim against lease 1's `next_due` and confirms the $3,400 checking balance can cover it before Facilities asks a human to approve the payment. |
| 101 | Invoice 501 to Bulldog Print Co, $840, due 2026-08-28 → `days_until_due: -3`, overdue; total due $3,240 vs. cash $3,400 → $160 left | Unblocking Tauhid's tee means paying invoice 501 first, and this tool shows Accounting it's overdue and that paying it along with the rent still leaves $160, so both payments can go to the human for approval without overdrawing. |

## MCP connection and tool tests (Problem 4)

Connection: `.mcp.json` at the project root registers server `campus-customs` (stdio) → `.venv/Scripts/python.exe mcp_server/server.py`, with `CAMPUS_DB` = `data/campus_customs_new.db`. FastMCP 4.0.11 installed in the project `.venv`.

Tested by connecting with a FastMCP client using `.mcp.json` and calling each tool over MCP (shop today 2026-08-31). Server listed `check_stock`, `check_vendor_restock`, `list_bills_due`.

| Call | Result | Ticket |
|---|---|---|
| `check_stock("CC-TEE-WHITE","S",1)` | in_stock 0, shortfall 1, margin 71.4% | 101 ✅ |
| `check_stock("CC-HOOD-NAVY","M",20)` | in_stock 8, shortfall 12, cost $22 / list $58, margin 62.1% | 103 ✅ |
| `check_vendor_restock(1)` | Bulldog Print `can_ship: false`, invoice 501 $840, 3 days overdue | 101, 103 ✅ |
| `check_vendor_restock()` | 3 vendors; Elm City Gifts ETA 2026-09-03, QuickShip CT 2026-09-01 | 103 ✅ |
| `list_bills_due()` | invoice 501 (−3 days, overdue) + rent $2,400 (+2 days); total $3,240 vs. cash $3,400 → $160 left | 101, 102 ✅ |

Database unchanged after all calls (byte-identical to the original).

## Agent team (Problem 5)

Pydantic AI, every agent on **gpt-6-luna** through the **Portkey** gateway (`https://api.portkey.ai/v1`, OpenAI Responses API, reasoning effort medium). *(Originally Claude Haiku 5.5; switched in Prompt 17 because there is no Anthropic key. Portkey routes to Azure OpenAI, where gpt-6-luna only supports tool calls with reasoning on the Responses API.)* The Portkey key lives only in the local, git-ignored `.env` at the project root. Prompts: `backend/prompts/<agent>.md` (one per agent). Types: `backend/models.py`. Agents: `backend/boss.py`, `inventory.py`, `accounting.py`, `facilities.py`, `customer_service.py`. Wiring and loops: `backend/team.py`.

| Agent | MCP tools it can see | Returns |
|---|---|---|
| Boss | `get_ticket`, `list_open_tickets`, `list_bills_due`, `list_approvals`, `update_ticket_status` | `BossDecision` |
| Inventory | `get_ticket`, `check_stock`, `check_vendor_restock`, `create_purchase_order` | `InventoryReport` |
| Accounting | `get_ticket`, `list_bills_due`, `list_approvals`, `request_payment`, `check_stock`, `quote_discount`, `check_vendor_restock` | `AccountingReport` |
| Facilities | `get_ticket`, `get_lease`, `list_bills_due`, `list_approvals`, `request_payment` | `FacilitiesReport` |
| Customer Service | `get_ticket`, `save_draft_message` | `CustomerMessageReport` |

- **Full connectivity:** each agent has `ask_<teammate>` tools for all four others (20 delegation edges). A delegation is refused if the target is already in the chain (no A→B→A loops) or the chain is 3 deep.
- **Human-only tools** (`approve_and_pay`, `reject_payment`, `approve_purchase_order`) are filtered out of every agent's toolset (`backend/shared.py` raises if one is ever granted), and the server refuses them if `approved_by` is an agent name.
- **Loops:** `run_ticket(id)` makes the Boss work one ticket. `run_all_open_tickets()` resets the database, then works every open ticket in board order. Every delegation and MCP tool call is recorded as an `AgentEvent` for the dashboard feed.
- **Expected results** per ticket, written before running: `output/desk_tickets.html`.

## Backend routes (Problem 7)

`backend/main.py` (FastAPI). Start it from `backend/` with `uvicorn main:app --reload --port 8000`, which serves http://localhost:8000. Interactive docs are at `/docs`.

- `GET  http://localhost:8000/tickets`: returns all three tickets with their status and whether each is `open` or `resolved` (plus whether the team is running on it and its last Boss decision).
- `GET  http://localhost:8000/tickets/{id}`: returns one ticket with its linked rows and the team's work on it (approvals, POs, drafts, status history).
- `POST http://localhost:8000/tickets/{id}/run`: runs the agent team (Boss first) on that ticket in the background. Add `?wait=true` to block until it finishes. One run at a time.
- `GET  http://localhost:8000/events?since={last_id}&ticket_id={id}`: returns recent agent events (who asked whom, what each agent answered, and every MCP tool call and result) so the board can refresh.
- `GET  http://localhost:8000/approvals?status=pending`: returns payment requests and draft purchase orders waiting for a human.
- `POST http://localhost:8000/approve` `{kind: "payment"|"purchase_order", id, approved_by}`: a human approves. For a payment, this is the **only** route that moves cash. It writes `payments`, debits checking, marks the invoice paid or moves rent forward, and refuses if cash is short or `approved_by` is an agent.
- `POST http://localhost:8000/reject` `{id, rejected_by, note}`: a human rejects a pending payment request. No money moves.
- `GET  http://localhost:8000/cash`: returns the current checking balance from `cash_accounts`.
- `POST http://localhost:8000/reset`: copies the original database over the working copy and clears the event feed, for a fresh run.

## Dashboard (Problem 8)

`frontend/` (React + Vite + TypeScript). Run `npm run dev` from `frontend/` to open http://localhost:5173. It calls the backend at `http://localhost:8000` (`frontend/.env`). The backend allows only the Vite origins (`http://localhost:5173`, `http://127.0.0.1:5173`, plus `:4173` for `vite preview`). Design rationale: `output/design.md`.

| Requirement | Where on the board | Route(s) |
|---|---|---|
| List all three tickets | Ticket Lanes (left) | `GET /tickets` |
| Pick a ticket and start the team | Click a lane, then **LAUNCH TEAM** | `POST /tickets/{id}/run` |
| Each agent and what it's saying/doing | Playfield bumpers + comm cards + Transmission Log | `GET /events?since=` |
| Ticket marked resolved when the run finishes | Lane lamp turns green + RESOLVED chip; debrief stamp | `GET /tickets` (`state`) |
| Short summary of what each ticket did | Mission Debrief | `GET /tickets` (`last_decision`) |
| Human approves a payment or purchase | Approval Console flippers | `GET /approvals`, `POST /approve`, `POST /reject` |
| Checking balance drops after an approved payment | LED score panel (counts down, −$ drop) | `GET /cash` |
| Fresh run | **NEW GAME · RESET DB** | `POST /reset` |

## All MCP tools (`mcp_server/server.py`)

18 tools: 15 the agents or backend can use, plus 3 human-only. Every tool reads `desk.date_today` as today where dates matter, and none invents data.

| # | Tool | Reads | Writes | Used by | Tickets |
|---|---|---|---|---|---|
| 1 | `check_stock(sku, size, qty_needed)` | inventory, pricing | — | Inventory, Accounting | 101, 103 |
| 2 | `check_vendor_restock(vendor_id?)` | vendors, invoices, desk | — | Inventory, Accounting | 101, 103 |
| 3 | `list_bills_due()` | invoices, vendors, leases, cash_accounts, desk | — | Boss, Accounting, Facilities | 101, 102, 103 |
| 4 | `list_tickets()` | tickets, ticket_updates | — | backend (`GET /tickets`) | all |
| 5 | `list_open_tickets()` | tickets | — | Boss, `run_all_open_tickets` | all |
| 6 | `get_ticket(ticket_id)` | tickets + linked inventory, pricing, invoices, vendors, leases + approvals, POs, drafts, history | — | all agents | all |
| 7 | `update_ticket_status(ticket_id, status, note, author)` | tickets | tickets.status, ticket_updates | Boss | all |
| 8 | `get_lease(lease_id)` | leases, payments, desk | — | Facilities | 102 |
| 9 | `quote_discount(sku, qty, discount_pct)` | pricing | — | Accounting | 103 |
| 10 | `create_purchase_order(vendor_id, sku, size, qty, ticket_id, created_by)` | vendors, invoices, inventory, pricing, desk | purchase_orders (draft) | Inventory | 101 (PO #1), 103 |
| 11 | `request_payment(kind, ref_id, ticket_id, reason, requested_by)` | invoices / leases, cash_accounts, approvals | approvals (pending) | Accounting, Facilities | 101 (#1), 102 (#2) |
| 12 | `list_approvals(status?)` | approvals, cash_accounts | — | Boss, Accounting, Facilities, backend | all |
| 13 | `save_draft_message(ticket_id, recipient, subject, body, author)` | tickets | drafts | Customer Service | 101, 103 |
| 14 | `get_cash_balance(account)` | cash_accounts | — | backend (`GET /cash`) | — |
| 15 | `list_purchase_orders(status?)` | purchase_orders, vendors | — | backend (`GET /approvals`) | 101 |
| 16 | `approve_and_pay(approval_id, approved_by)` **human only** | approvals, invoices / leases, cash_accounts | payments, cash_accounts, invoices.status / leases.next_due, approvals | backend `POST /approve` | 101, 102 |
| 17 | `reject_payment(approval_id, rejected_by, note)` **human only** | approvals | approvals | backend `POST /reject` | — |
| 18 | `approve_purchase_order(po_id, approved_by)` **human only** | purchase_orders, invoices | purchase_orders.status | backend `POST /approve` | — |

Workflow tables the server creates in the working copy (a reset removes them): `approvals`, `purchase_orders`, `drafts`, `ticket_updates`.

## MCP tools added for the team (Problem 5)

| Tool | Reads / writes | Tickets |
|---|---|---|
| `get_ticket` | reads `tickets` + linked `inventory`, `pricing`, `invoices`, `vendors`, `leases` + workflow tables | 101, 102, 103 |
| `list_open_tickets` | reads `tickets` | all |
| `update_ticket_status` | writes `tickets.status`, `ticket_updates` | all |
| `get_lease` | reads `leases`, `payments`, `desk` | 102 |
| `quote_discount` | reads `pricing` | 103 |
| `create_purchase_order` | reads `vendors`, `invoices`, `inventory`, `pricing`, `desk`; writes `purchase_orders` | 101, 103 (after 501 is paid) |
| `request_payment` | reads `invoices`/`leases`, `cash_accounts`; writes `approvals` | 101 (invoice 501), 102 (rent) |
| `list_approvals` | reads `approvals`, `cash_accounts` | 101, 102, 103 |
| `save_draft_message` | writes `drafts` | 101, 103 (102 optional) |
| `approve_and_pay` (human) | writes `payments`, `cash_accounts`, `invoices`/`leases`, `approvals` | 101, 102 |
| `reject_payment` (human) | writes `approvals` | 101, 102 |

## Safety rules

Each rule is enforced in code, not just in a prompt:

| Rule | How it's enforced |
|---|---|
| **Only payments need human approval, and every payment does** | Agents only have `request_payment`, which writes a *pending* row to `approvals` and moves no money. `approve_and_pay` is human-only: filtered out of every agent's toolset, reachable only through `POST /approve`, and refused if `approved_by` is empty or an agent name. Everything else (routing, stock checks, discounts, PO drafts, message drafts, status) the agents do on their own. |
| **Pay tool refuses when cash is short; no negative balance** | `request_payment` refuses if the balance is below the bill. `approve_and_pay` re-checks inside a `BEGIN IMMEDIATE` transaction and refuses, marking the request `refused`, if `balance < amount`. Cash only goes out (no tool credits cash). |
| **A payment updates every related table** | In one transaction: `payments` row (with `approved_by`), `cash_accounts.balance` debited, then `invoices.status = 'paid'` or `leases.next_due` + 1 month, and `approvals.status = 'paid'`. |
| **Amounts come from the database, not the agent** | `request_payment` looks up the amount and payee itself; `approve_and_pay` refuses if the bill changed since the request. |
| **Today is `desk.date_today`** | Every date calculation uses `_shop_today()` (2026-08-31), never the system clock. |
| **Lead times come from `vendors.lead_days`** | `check_vendor_restock` / `create_purchase_order` compute arrival = shop today + lead_days. |
| **A vendor with an open invoice won't ship** | `check_vendor_restock` reports `can_ship: false`; `create_purchase_order` and `approve_purchase_order` refuse while any invoice for that vendor is open. |
| **No duplicate payment requests** | `request_payment` refuses a second pending request for the same bill. |
| **Never contact customers or vendors** | No tool sends anything. Messages go to `drafts` and POs to `purchase_orders` with status `draft` / `approved`; they stay on the board. |
| **Reset before a full run** | `POST /reset` (and `run_all_open_tickets(reset=True)`) copy the original DB over the working copy; refused while a run is in progress. |
| **One run at a time** | The backend refuses a second run while one is active (cash is shared). |
| **No delegation loops** | `ask_<agent>` refuses a teammate already in the chain and caps depth at 3. |
| **Secrets stay local** | The Portkey key is read from the git-ignored `.env`, sent only to `api.portkey.ai`, and never logged (redacted in `AI_prompts.md`). Portkey's response cache is bypassed (`x-portkey-cache-force-refresh`) so every run is a real decision. |
| **CORS** | The backend only accepts browser calls from the Vite origins (`localhost:5173` / `127.0.0.1:5173`, `:4173`). |
| **Everything is audited** | Every agent run (with its full event stream), human decision, and reset is appended to `output/audit_trail.json`. |

## Full run results (Problem 9)

Reset → **checking $3,400.00**. Tickets run in board order **101 → 103 → 102**. The human (JZ) then approved both payments on the dashboard, and each ticket got a follow-up pass. Ending **checking $160.00**, which matches `cash_accounts`.

| Ticket | Agents used | Human approval | Cash | Final status |
|---|---|---|---|---|
| 101 | Boss → Inventory → Accounting → Customer Service | Payment #1 invoice 501, $840 (JZ) | −$840.00 | waiting_vendor (PO #1 drafted: 1 tee, $8, ETA 2026-09-05) |
| 103 | Boss → Inventory → Accounting → Customer Service | none | $0.00 | waiting_customer (10% offer: $52.20 × 20 = $1,044) |
| 102 | Boss → Facilities | Payment #2 rent, $2,400 (JZ) | −$2,400.00 | resolved (lease next_due → 2026-10-02) |

Details: `output/desk_tickets.html` (Expected vs. Actual per ticket + Cash ledger), `output/resolved_tickets.json`, `output/resolved_board.html` (dashboard screenshots), `output/audit_trail.json`.
