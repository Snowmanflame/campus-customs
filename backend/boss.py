"""Boss agent: reads each ticket, routes it to specialists, makes the final call."""

from pydantic_ai import Agent

from .models import BossDecision, TeamDeps
from .shared import MODEL, MODEL_SETTINGS, load_prompt, mcp_tools_for

NAME = "boss"
TOOLS = frozenset({
    "get_ticket",
    "list_open_tickets",
    "list_bills_due",
    "list_approvals",
    "update_ticket_status",
})

boss_agent = Agent(
    MODEL,
    name=NAME,
    deps_type=TeamDeps,
    output_type=BossDecision,
    instructions=load_prompt(NAME),
    toolsets=[mcp_tools_for(NAME, TOOLS)],
    model_settings=MODEL_SETTINGS,
    retries=2,
)
