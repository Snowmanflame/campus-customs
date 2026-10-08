"""Accounting agent: cash, invoices, margins; prepares payments for human approval."""

from pydantic_ai import Agent

from .models import AccountingReport, TeamDeps
from .shared import MODEL, MODEL_SETTINGS, load_prompt, mcp_tools_for

NAME = "accounting"
TOOLS = frozenset({
    "get_ticket",
    "list_bills_due",
    "list_approvals",
    "request_payment",
    "check_stock",
    "quote_discount",
    "check_vendor_restock",
})

accounting_agent = Agent(
    MODEL,
    name=NAME,
    deps_type=TeamDeps,
    output_type=AccountingReport,
    instructions=load_prompt(NAME),
    toolsets=[mcp_tools_for(NAME, TOOLS)],
    model_settings=MODEL_SETTINGS,
    retries=2,
)
