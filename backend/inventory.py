"""Inventory agent: stock by SKU + size, shortfalls, restock vendor and lead time, draft POs."""

from pydantic_ai import Agent

from .models import InventoryReport, TeamDeps
from .shared import MODEL, MODEL_SETTINGS, load_prompt, mcp_tools_for

NAME = "inventory"
TOOLS = frozenset({
    "get_ticket",
    "check_stock",
    "check_vendor_restock",
    "create_purchase_order",
})

inventory_agent = Agent(
    MODEL,
    name=NAME,
    deps_type=TeamDeps,
    output_type=InventoryReport,
    instructions=load_prompt(NAME),
    toolsets=[mcp_tools_for(NAME, TOOLS)],
    model_settings=MODEL_SETTINGS,
    retries=2,
)
