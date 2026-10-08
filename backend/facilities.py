"""Facilities agent: the shop space - lease, rent, landlord; prepares rent for human approval."""

from pydantic_ai import Agent

from .models import FacilitiesReport, TeamDeps
from .shared import MODEL, MODEL_SETTINGS, load_prompt, mcp_tools_for

NAME = "facilities"
TOOLS = frozenset({
    "get_ticket",
    "get_lease",
    "list_bills_due",
    "list_approvals",
    "request_payment",
})

facilities_agent = Agent(
    MODEL,
    name=NAME,
    deps_type=TeamDeps,
    output_type=FacilitiesReport,
    instructions=load_prompt(NAME),
    toolsets=[mcp_tools_for(NAME, TOOLS)],
    model_settings=MODEL_SETTINGS,
    retries=2,
)
