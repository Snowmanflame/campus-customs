# Campus Customs MCP Server

**What it is for:** This is the single gateway between the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service) and the shop's data. Agents never open the database themselves — every lookup goes through a tool on this server, so all agents see the same numbers and follow the same rules.

**Database:** `data/campus_customs_new.db` (the working copy). The original `data/campus_customs.db` is never touched; copy it over the working file to reset before each full run. Override the path with the `CAMPUS_DB` environment variable if needed.

**Rules baked in:** "today" is always `desk.date_today` (not the system clock); a vendor with an open invoice cannot ship; tools only return what is in the database.

## Tools

Core lookups (Problem 3):

| Tool | What it does |
|---|---|
| `check_stock(sku, size, qty_needed=1)` | On-hand qty and location for one SKU + size, the shortfall against `qty_needed`, and unit cost / list price / margin. |
| `check_vendor_restock(vendor_id=None)` | Per vendor: specialty, lead days, open invoices (days overdue), whether it can ship, and earliest arrival date (`date_today + lead_days`). |
| `list_bills_due()` | All open vendor invoices and lease rent with due dates and days until due (negative = overdue), plus cash balances and whether cash covers them. Read-only — it never pays. |

Added for the agent team (Problem 5):

| Tool | Used by | What it does |
|---|---|---|
| `list_open_tickets()` | Boss | Tickets not resolved/closed. |
| `get_ticket(ticket_id)` | all | Ticket + linked inventory, pricing, invoice, vendor, lease + approvals, POs, drafts, status history. |
| `update_ticket_status(ticket_id, status, note, author)` | Boss | Changes status and logs the reason in `ticket_updates`. |
| `get_lease(lease_id)` | Facilities | Lease row, days until rent is due, rent payments on record. |
| `quote_discount(sku, qty, discount_pct)` | Accounting | Discounted price, margin, profit, below-cost flag, max discount before loss. |
| `create_purchase_order(vendor_id, sku, size, qty, ticket_id, created_by)` | Inventory | Draft PO (never sent, no cash). **Refused if the vendor has an open invoice.** |
| `request_payment(kind, ref_id, ticket_id, reason, requested_by)` | Accounting, Facilities | Queues an invoice or rent payment for human approval. Amount comes from the DB. Refuses on short cash or duplicates. Moves no money. |
| `list_approvals(status=None)` | Boss, Accounting, Facilities | The approval queue plus cash balances. |
| `save_draft_message(ticket_id, recipient, subject, body, author)` | Customer Service | Saves a draft to the board. Never sent. |
| `approve_and_pay(approval_id, approved_by)` | **Human only** (dashboard) | Pays a pending request: refuses agent names, non-pending requests, and insufficient cash (no negative balance). Writes `payments`, debits `cash_accounts`, marks the invoice paid or moves the lease `next_due` forward a month, all in one transaction. |
| `reject_payment(approval_id, rejected_by, note)` | **Human only** | Rejects a pending request. |
| `list_tickets()` | backend | Every ticket, any status. |
| `get_cash_balance(account="checking")` | backend | Current balance from `cash_accounts`. |
| `list_purchase_orders(status=None)` | backend | Draft/approved POs with vendor names. |
| `approve_purchase_order(po_id, approved_by)` | **Human only** | Marks a draft PO approved (re-checks the vendor isn't blocked). No cash moves; nothing is sent. |

The server adds four workflow tables to the working copy on first use: `approvals`, `purchase_orders`, `drafts`, `ticket_updates`. A reset removes them again.

## Run (later)

```bash
pip install -r mcp_server/requirements.txt
python mcp_server/server.py
```
