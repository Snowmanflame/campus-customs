"""Smoke-test every MCP tool over the real MCP connection in .mcp.json.

Each call's output is cross-checked against direct SQL on data/campus_customs_new.db.
Evidence is written to output/mcp_smoke.json.

    .venv/Scripts/python mcp_server/smoke_test.py
"""

import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.shared import mcp_config  # noqa: E402  (resolves .mcp.json paths for this machine)

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
OUT = ROOT / "output" / "mcp_smoke.json"


def q(sql, *args):
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(sql, args)]
    conn.close()
    return rows


def check(label, tool_value, db_value):
    return {"field": label, "tool": tool_value, "db": db_value, "match": tool_value == db_value}


def verify_check_stock(out, sku, size, qty_needed):
    inv = q("SELECT qty, location, name FROM inventory WHERE sku=? AND size=?", sku, size)[0]
    pr = q("SELECT unit_cost, list_price FROM pricing WHERE sku=?", sku)[0]
    return {
        "sql": [
            f"SELECT qty, location, name FROM inventory WHERE sku='{sku}' AND size='{size}'",
            f"SELECT unit_cost, list_price FROM pricing WHERE sku='{sku}'",
        ],
        "checks": [
            check("in_stock = inventory.qty", out["in_stock"], inv["qty"]),
            check("location = inventory.location", out["location"], inv["location"]),
            check("name = inventory.name", out["name"], inv["name"]),
            check("shortfall = max(qty_needed - inventory.qty, 0)", out["shortfall"], max(qty_needed - inv["qty"], 0)),
            check("pricing.unit_cost", out["pricing"]["unit_cost"], pr["unit_cost"]),
            check("pricing.list_price", out["pricing"]["list_price"], pr["list_price"]),
        ],
    }


def verify_vendor_restock(out):
    today = q("SELECT date_today FROM desk")[0]["date_today"]
    checks = [check("shop_today = desk.date_today", out["shop_today"], today)]
    for v in out["vendors"]:
        row = q("SELECT name, specialty, lead_days FROM vendors WHERE id=?", v["vendor_id"])[0]
        open_ids = [r["id"] for r in q("SELECT id FROM invoices WHERE vendor_id=? AND status='open'", v["vendor_id"])]
        vid = v["vendor_id"]
        checks += [
            check(f"vendor {vid} name", v["name"], row["name"]),
            check(f"vendor {vid} specialty", v["specialty"], row["specialty"]),
            check(f"vendor {vid} lead_days", v["lead_days"], row["lead_days"]),
            check(f"vendor {vid} open invoice ids", [i["invoice_id"] for i in v["open_invoices"]], open_ids),
            check(f"vendor {vid} can_ship = (no open invoices)", v["can_ship"], not open_ids),
        ]
        for i in v["open_invoices"]:
            inv = q("SELECT amount, due_date FROM invoices WHERE id=?", i["invoice_id"])[0]
            checks += [
                check(f"invoice {i['invoice_id']} amount", i["amount"], inv["amount"]),
                check(f"invoice {i['invoice_id']} due_date", i["due_date"], inv["due_date"]),
            ]
    return {
        "sql": [
            "SELECT date_today FROM desk",
            "SELECT name, specialty, lead_days FROM vendors WHERE id=?",
            "SELECT id, amount, due_date FROM invoices WHERE vendor_id=? AND status='open'",
        ],
        "checks": checks,
    }


def verify_bills_due(out):
    today = q("SELECT date_today FROM desk")[0]["date_today"]
    inv = q("SELECT id, amount, due_date FROM invoices WHERE status='open'")
    leases = q("SELECT id, monthly_rent, next_due FROM leases")
    cash = q("SELECT SUM(balance) AS total FROM cash_accounts")[0]["total"]
    bills = {(b["kind"], b["ref_id"]): b for b in out["bills"]}
    checks = [check("shop_today = desk.date_today", out["shop_today"], today)]
    for i in inv:
        b = bills.get(("invoice", i["id"]), {})
        checks += [
            check(f"invoice {i['id']} amount", b.get("amount"), i["amount"]),
            check(f"invoice {i['id']} due_date", b.get("due_date"), i["due_date"]),
        ]
    for l in leases:
        b = bills.get(("rent", l["id"]), {})
        checks += [
            check(f"lease {l['id']} rent", b.get("amount"), l["monthly_rent"]),
            check(f"lease {l['id']} next_due", b.get("due_date"), l["next_due"]),
        ]
    total_due = sum(i["amount"] for i in inv) + sum(l["monthly_rent"] for l in leases)
    checks += [
        check("bill count = open invoices + leases", len(out["bills"]), len(inv) + len(leases)),
        check("total_cash = SUM(cash_accounts.balance)", out["total_cash"], cash),
        check("total_due", out["total_due"], total_due),
        check("cash_left_if_all_paid", out["cash_left_if_all_paid"], cash - total_due),
    ]
    return {
        "sql": [
            "SELECT date_today FROM desk",
            "SELECT id, amount, due_date FROM invoices WHERE status='open'",
            "SELECT id, monthly_rent, next_due FROM leases",
            "SELECT SUM(balance) FROM cash_accounts",
        ],
        "checks": checks,
    }


TESTS = [
    {
        "ticket": 101,
        "prompt": "Use the campus-customs check_stock tool to see whether we have 1 Classic Bulldog Tee (CC-TEE-WHITE) in size S for Tauhid's order, ticket 101.",
        "tool": "check_stock",
        "args": {"sku": "CC-TEE-WHITE", "size": "S", "qty_needed": 1},
        "verify": lambda out: verify_check_stock(out, "CC-TEE-WHITE", "S", 1),
    },
    {
        "ticket": 103,
        "prompt": "Use check_stock to see if we can fill the Yale AI Club's request for 20 navy hoodies (CC-HOOD-NAVY) in size M, ticket 103, and show me the margin.",
        "tool": "check_stock",
        "args": {"sku": "CC-HOOD-NAVY", "size": "M", "qty_needed": 20},
        "verify": lambda out: verify_check_stock(out, "CC-HOOD-NAVY", "M", 20),
    },
    {
        "ticket": "101, 103",
        "prompt": "Use check_vendor_restock to tell me whether our vendors can ship a restock right now, their lead times, and whether any open invoice is blocking them.",
        "tool": "check_vendor_restock",
        "args": {},
        "verify": verify_vendor_restock,
    },
    {
        "ticket": "101, 102",
        "prompt": "Use list_bills_due to list every open bill (invoices and rent) with how many days until it's due, and whether our cash covers them.",
        "tool": "list_bills_due",
        "args": {},
        "verify": verify_bills_due,
    },
]


async def main():
    cfg = mcp_config()
    results = []
    async with Client(cfg) as client:
        listed = [t.name for t in await client.list_tools()]
        for t in TESTS:
            res = await client.call_tool(t["tool"], t["args"])
            out = res.structured_content if res.structured_content is not None else res.data
            v = t["verify"](out)
            results.append({
                "ticket": t["ticket"],
                "prompt": t["prompt"],
                "tool": t["tool"],
                "args": t["args"],
                "output": out,
                "db_verification": {**v, "all_match": all(c["match"] for c in v["checks"])},
            })
    evidence = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "database": "data/campus_customs_new.db",
        "connection": ".mcp.json -> campus-customs (stdio, FastMCP)",
        "tools_listed_by_server": listed,
        "all_tests_pass": all(r["db_verification"]["all_match"] for r in results),
        "tests": results,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2))
    for r in results:
        dv = r["db_verification"]
        print(f"{r['tool']:22} ticket {r['ticket']!s:9} {sum(c['match'] for c in dv['checks'])}/{len(dv['checks'])} checks match")
    print("ALL PASS" if evidence["all_tests_pass"] else "FAILURES PRESENT", "->", OUT)


if __name__ == "__main__":
    asyncio.run(main())
